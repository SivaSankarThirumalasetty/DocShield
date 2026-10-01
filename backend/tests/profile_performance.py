import time
import os
import sys
import psutil
import json
import asyncio
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from PIL import Image

def get_memory_mb():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

def profile_docshield():
    print("=" * 70)
    print("  DOCSHIELD PERFORMANCE & RESOURCE CONSUMPTION PROFILE")
    print("=" * 70)

    # 1. Startup Time Measurement
    t0 = time.perf_counter()
    from backend.core.config import settings
    from backend.services.ocr_service import ocr_service
    from backend.services.document_parser import document_parser
    from backend.services.face_service import face_service
    from backend.services.tampering_service import tampering_service
    from backend.services.risk_engine import risk_engine
    from backend.services.storage_service import storage_service
    startup_time_sec = time.perf_counter() - t0
    
    initial_ram_mb = get_memory_mb()
    print(f"[*] Cold Module Startup Time: {startup_time_sec:.3f} s")
    print(f"[*] Base Process Memory (RSS): {initial_ram_mb:.1f} MB")

    # 2. Warm-up & Pipeline Latency Benchmarking
    sample_passport = Path(__file__).resolve().parent.parent.parent / "sample_data" / "passport_sample.png"
    sample_person = Path(__file__).resolve().parent.parent.parent / "sample_data" / "sample_person.png"
    
    if not sample_passport.exists():
        print(f"[!] Fixture not found: {sample_passport}")
        return

    from backend.utils.image_utils import bytes_to_cv2, cv2_to_pil, deskew, resize_if_larger

    doc_bytes = sample_passport.read_bytes()
    person_bytes = sample_person.read_bytes() if sample_person.exists() else None

    latencies = []
    cpu_measurements = []

    print("[*] Running 3 benchmark iterations of full verification pipeline...")
    
    for i in range(3):
        t_iter_start = time.perf_counter()
        
        # Preprocessing
        cv_doc = bytes_to_cv2(doc_bytes)
        cv_doc = resize_if_larger(cv_doc, max_dim=1600)
        cv_doc, _ = deskew(cv_doc)
        pil_doc = cv2_to_pil(cv_doc)
        
        cv_person = None
        if person_bytes:
            cv_person = bytes_to_cv2(person_bytes)
            cv_person = resize_if_larger(cv_person, max_dim=1200)

        # Pipeline stages
        ocr_res = ocr_service.extract_text(pil_doc)
        doc_info = document_parser.parse(ocr_res, doc_type_hint="PASSPORT")
        tamper_res = tampering_service.analyze(pil_doc)
        face_res = face_service.verify_faces(cv_doc, cv_person)
        
        latency_ms = (time.perf_counter() - t_iter_start) * 1000
        latencies.append(latency_ms)
        cpu_measurements.append(psutil.cpu_percent(interval=None))
        print(f"    - Iteration {i+1}: {latency_ms:.1f} ms | Current RAM: {get_memory_mb():.1f} MB")

    peak_ram_mb = get_memory_mb()
    ram_delta_mb = peak_ram_mb - initial_ram_mb
    avg_latency_ms = sum(latencies) / len(latencies)

    # 3. Minimum Practical Hosting Sizing
    # Models in memory: EasyOCR (PyTorch), dlib ResNet (128-d), OpenCV, FastAPI
    # Safe minimum RAM: Peak RAM * 1.5 buffer + OS overhead (~1.5GB to 2GB recommended)
    min_ram_recommended_mb = max(2048, int(peak_ram_mb * 1.8))
    min_vcpu_recommended = 2

    report = {
        "startup_time_seconds": round(startup_time_sec, 3),
        "initial_memory_mb": round(initial_ram_mb, 1),
        "peak_memory_mb": round(peak_ram_mb, 1),
        "memory_delta_mb": round(ram_delta_mb, 1),
        "average_analysis_latency_ms": round(avg_latency_ms, 1),
        "iteration_latencies_ms": [round(l, 1) for l in latencies],
        "hosting_recommendations": {
            "minimum_ram_mb": min_ram_recommended_mb,
            "minimum_ram_gb": round(min_ram_recommended_mb / 1024, 1),
            "minimum_vcpu": min_vcpu_recommended,
            "recommended_concurrency": 2,
            "runtime_environment": "Python 3.11 / Linux (Ubuntu 22.04 LTS container)"
        }
    }

    report_path = Path(__file__).resolve().parent / "performance_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n" + "=" * 70)
    print("  RESOURCE SIZING & HOSTING SPECIFICATIONS")
    print("=" * 70)
    print(f"Peak Process Memory (RSS):          {peak_ram_mb:.1f} MB")
    print(f"Average Pipeline Latency:           {avg_latency_ms:.1f} ms")
    print(f"Minimum Practical RAM Required:     {min_ram_recommended_mb} MB ({report['hosting_recommendations']['minimum_ram_gb']} GB)")
    print(f"Minimum Recommended vCPU:           {min_vcpu_recommended} vCPUs")
    print(f"Recommended Concurrency Cap:        {settings.max_concurrent_analysis} concurrent analyses (CPU bound)")
    print(f"Performance Report Saved to:        {report_path}")
    print("=" * 70)

if __name__ == "__main__":
    profile_docshield()
