import os
import sys
import time
import json
from pathlib import Path
from PIL import Image
import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.services.ocr_service import ocr_service
from backend.services.document_parser import document_parser
from backend.services.validation_service import validation_service
from backend.services.tampering_service import tampering_service
from backend.services.face_service import face_service
from backend.services.mock_database import db_service
from backend.services.risk_engine import risk_engine

SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent / "sample_data"

def run_evaluation():
    print("=" * 70)
    print("DOCSHIELD AI/CV PIPELINE EMPIRICAL EVALUATION")
    print("Statement: Not validated for production accuracy.")
    print("Status: Benchmark executed on sample reference dataset.")
    print("=" * 70)

    sample_files = [
        {"name": "passport_sample.png", "expected_type": "PASSPORT", "is_valid": True},
        {"name": "aadhaar_valid.png", "expected_type": "AADHAAR", "is_valid": True},
        {"name": "aadhaar_invalid_checksum.png", "expected_type": "AADHAAR", "is_valid": False},
    ]

    person_sample = SAMPLE_DIR / "sample_person.png"
    cv_person = cv2.imread(str(person_sample)) if person_sample.exists() else None

    results = []
    total_start = time.time()

    for item in sample_files:
        filepath = SAMPLE_DIR / item["name"]
        if not filepath.exists():
            print(f"[-] Warning: Sample file {item['name']} not found at {filepath}")
            continue

        start_t = time.time()
        pil_img = Image.open(filepath)
        cv_img = cv2.imread(str(filepath))

        # 1. OCR
        ocr_out = ocr_service.extract_text(pil_img)
        ocr_success = ocr_out.get("success", False)
        ocr_conf = ocr_out.get("ocr_confidence", 0.0)

        # 2. Parsing & Classification
        doc_info = document_parser.parse(ocr_out)
        class_match = (doc_info.document_type == item["expected_type"])

        # 3. Checksums & Validation
        val_out = validation_service.validate_document(doc_info)
        val_match = (val_out.overall_valid == item["is_valid"])

        # 4. Tampering ELA
        tamper_out = tampering_service.analyze(pil_img)

        # 5. Biometric Face
        face_out = face_service.verify_faces(cv_img, cv_person)

        # 6. Database / Watchlist
        watch_out = db_service.check_watchlist(name=doc_info.name, doc_number=doc_info.document_number)

        # 7. Risk Engine
        risk_out = risk_engine.evaluate(doc_info, val_out, watch_out, tamper_out, face_out)

        elapsed = round((time.time() - start_t) * 1000.0, 1)

        record = {
            "file": item["name"],
            "expected_type": item["expected_type"],
            "detected_type": doc_info.document_type,
            "classification_correct": class_match,
            "ocr_success": ocr_success,
            "ocr_confidence": ocr_conf,
            "extracted_doc_number": doc_info.document_number,
            "validation_valid": val_out.overall_valid,
            "expected_valid": item["is_valid"],
            "checksum_validation_correct": val_match,
            "tamper_ela_score": tamper_out.ela_score,
            "face_detected": face_out.document_face_detected,
            "face_verdict": face_out.match_verdict,
            "risk_score": risk_out.score,
            "risk_tier": risk_out.level,
            "processing_time_ms": elapsed
        }
        results.append(record)
        print(f"[+] Sample: {item['name']:<28} | Type: {doc_info.document_type:<8} | OCR Conf: {ocr_conf:4.1f}% | Risk: {risk_out.score:2d} ({risk_out.level}) | Time: {elapsed:5.1f}ms")

    total_time = round(time.time() - total_start, 2)
    n_samples = len(results)

    if n_samples == 0:
        print("[!] No samples evaluated.")
        return

    # Compute empirical rates
    ocr_rate = sum(1 for r in results if r["ocr_success"]) / n_samples * 100.0
    class_rate = sum(1 for r in results if r["classification_correct"]) / n_samples * 100.0
    val_rate = sum(1 for r in results if r["checksum_validation_correct"]) / n_samples * 100.0
    face_det_rate = sum(1 for r in results if r["face_detected"]) / n_samples * 100.0
    mean_latency = sum(r["processing_time_ms"] for r in results) / n_samples

    print("\n" + "=" * 70)
    print("EMPIRICAL EVALUATION SUMMARY (N = %d)" % n_samples)
    print("=" * 70)
    print(f"OCR Character Recognition Rate:       {ocr_rate:.1f}%")
    print(f"Document Classification Accuracy:     {class_rate:.1f}%")
    print(f"Checksum & Validation Accuracy:       {val_rate:.1f}%")
    print(f"Document Portrait Detection Rate:     {face_det_rate:.1f}%")
    print(f"Average Pipeline Latency:             {mean_latency:.1f} ms")
    print(f"Total Benchmark Time:                 {total_time} s")
    print("-" * 70)
    print("NOTE: Sample size is limited to reference fixtures. Results reflect functional")
    print("pipeline validation only and are NOT validated for production population accuracy.")
    print("=" * 70)

    # Output JSON summary report
    report_path = Path(__file__).resolve().parent / "evaluation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "statement": "Not validated for production accuracy.",
            "sample_count": n_samples,
            "ocr_rate_pct": ocr_rate,
            "classification_accuracy_pct": class_rate,
            "checksum_accuracy_pct": val_rate,
            "face_detection_pct": face_det_rate,
            "mean_latency_ms": mean_latency,
            "detailed_results": results
        }, f, indent=2)
    print(f"[i] Evaluation report exported to: {report_path.name}")

if __name__ == "__main__":
    run_evaluation()
