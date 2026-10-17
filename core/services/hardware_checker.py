from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class HardwareProfile:
    has_cuda: bool
    gpu_name: str
    total_vram_gb: float
    free_vram_gb: float
    ram_gb: float
    avail_ram_gb: float
    cpu_cores: int
    recommended_model: str
    recommended_compute: str
    stability_rating: str
    checks: List[Dict[str, Any]] = field(default_factory=list)


class HardwareChecker:
    """Detects system hardware and evaluates suitability for subtitle generation models."""

    @staticmethod
    def detect() -> HardwareProfile:
        has_cuda = False
        gpu_name = "None (CPU)"
        total_vram = 0.0
        free_vram = 0.0

        try:
            import torch
            if torch.cuda.is_available():
                has_cuda = True
                gpu_name = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                total_vram = props.total_memory / (1024 ** 3)
                free_vram = (props.total_memory - torch.cuda.memory_allocated(0)) / (1024 ** 3)
        except Exception:
            pass

        ram_gb = 8.0
        avail_ram = 4.0
        cpu_cores = 4
        try:
            import psutil
            ram_gb = psutil.virtual_memory().total / (1024 ** 3)
            avail_ram = psutil.virtual_memory().available / (1024 ** 3)
            cpu_cores = psutil.cpu_count(logical=True) or 4
        except Exception:
            pass

        checks: List[Dict[str, Any]] = []

        # 1. GPU Acceleration
        if has_cuda:
            checks.append({
                "feature": "GPU CUDA Acceleration",
                "can_run": True,
                "status": "ok",
                "detail": f"{gpu_name} ({total_vram:.1f} GB VRAM)",
            })
        else:
            checks.append({
                "feature": "GPU CUDA Acceleration",
                "can_run": False,
                "status": "warn",
                "detail": "Không có GPU CUDA (chạy bằng CPU, tốc độ sẽ chậm hơn)",
            })

        # 2. Silero VAD
        checks.append({
            "feature": "Timing Draft (Silero VAD)",
            "can_run": True,
            "status": "ok",
            "detail": "Sẵn sàng (tách câu nhanh, rất nhẹ trên CPU/GPU)",
        })

        # 3. Whisper Models
        checks.append({
            "feature": "Whisper Nhẹ (tiny, base, small)",
            "can_run": True,
            "status": "ok",
            "detail": "Chạy rất mượt trên cả CPU & GPU",
        })

        med_ok = (has_cuda and total_vram >= 3.0) or ram_gb >= 12
        checks.append({
            "feature": "Whisper Trung bình (medium)",
            "can_run": med_ok,
            "status": "ok" if med_ok else "warn",
            "detail": "Khả dụng" if med_ok else "Yêu cầu >= 4GB VRAM hoặc 12GB RAM",
        })

        turbo_ok = (has_cuda and total_vram >= 3.5) or ram_gb >= 16
        checks.append({
            "feature": "Whisper Tối ưu (large-v3-turbo)",
            "can_run": turbo_ok,
            "status": "ok" if turbo_ok else "warn",
            "detail": "Tốt nhất: Chất lượng tương đương large-v3 nhưng nhẹ và nhanh hơn" if turbo_ok else "Khuyên dùng GPU >= 4GB VRAM",
        })

        l3_ok = has_cuda and total_vram >= 5.8
        checks.append({
            "feature": "Whisper Đầy đủ (large-v3)",
            "can_run": l3_ok,
            "status": "ok" if l3_ok else "warn",
            "detail": "Chạy tốt trên GPU >= 6GB VRAM" if l3_ok else "Có thể tràn VRAM trên GPU < 6GB (nên dùng turbo)",
        })

        # Stability rating & recommendations
        if has_cuda and total_vram >= 5.8:
            rec_model = "large-v3-turbo"
            rec_compute = "float16"
            stability = "Rất mượt mà (GPU mạnh)"
        elif has_cuda and total_vram >= 3.5:
            rec_model = "large-v3-turbo"
            rec_compute = "int8_float16"
            stability = "Mượt mà & Tối ưu"
        elif has_cuda:
            rec_model = "small"
            rec_compute = "int8_float16"
            stability = "Ổn định"
        else:
            rec_model = "small" if ram_gb >= 8 else "base"
            rec_compute = "int8"
            stability = "Chế độ CPU (Chậm hơn)"

        return HardwareProfile(
            has_cuda=has_cuda,
            gpu_name=gpu_name,
            total_vram_gb=round(total_vram, 1),
            free_vram_gb=round(free_vram, 1),
            ram_gb=round(ram_gb, 1),
            avail_ram_gb=round(avail_ram, 1),
            cpu_cores=cpu_cores,
            recommended_model=rec_model,
            recommended_compute=rec_compute,
            stability_rating=stability,
            checks=checks,
        )
