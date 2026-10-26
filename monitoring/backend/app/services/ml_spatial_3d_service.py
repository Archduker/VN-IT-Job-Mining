# -*- coding: utf-8 -*-
"""Service tính toán tọa độ không gian 3D cho Machine Learning & Data Mining.

Cung cấp dữ liệu vector 3 chiều cho các thuật toán:
1. UMAP / t-SNE 3D Semantic Vector Space (phân cụm Job Family SD2).
2. Isolation Forest 3D Anomaly Boundary (phát hiện tin rác SD5).
"""

import math
import random
from typing import Any, Dict, List


class MLSpatial3DService:
    """Xử lý và sinh dữ liệu kết xuất không gian 3D (WebGL Plotly)."""

    def get_umap_3d_clusters(self, sample_size: int = 150) -> Dict[str, Any]:
        """Sinh tọa độ không gian 3D cho các cụm nghề nghiệp từ vector nhúng."""
        # Giả lập cụm phân bổ tự nhiên trong không gian 3D dựa trên mô hình Sentence-Transformers
        families = [
            {"name": "Backend & Cloud", "center": (-3.0, 2.0, 1.5), "skills": ["Java", "Go", "Docker", "AWS", "Kafka"]},
            {"name": "Data & AI", "center": (3.5, 3.0, 2.0), "skills": ["Python", "PyTorch", "Spark", "SQL", "LLM"]},
            {"name": "Frontend & Mobile", "center": (-2.0, -3.5, -1.0), "skills": ["React", "TypeScript", "Flutter", "Next.js"]},
            {"name": "DevOps & Security", "center": (0.5, 1.0, -3.0), "skills": ["Kubernetes", "Terraform", "CI/CD", "Linux"]},
        ]

        random.seed(42)
        points = []
        idx = 0

        for fam in families:
            cx, cy, cz = fam["center"]
            pts_per_fam = sample_size // len(families)
            for _ in range(pts_per_fam):
                idx += 1
                # Gaussian noise xung quanh tâm cụm
                x = round(cx + random.gauss(0, 0.75), 3)
                y = round(cy + random.gauss(0, 0.75), 3)
                z = round(cz + random.gauss(0, 0.75), 3)
                sal = round(random.uniform(20.0, 65.0), 1)

                points.append({
                    "id": f"job_vec_{idx}",
                    "title": f"Senior {fam['name']} Engineer",
                    "company": f"Tech Company #{random.randint(10, 99)}",
                    "job_family": fam["name"],
                    "salary_vnd": sal,
                    "x": x,
                    "y": y,
                    "z": z,
                    "is_anomaly": False,
                    "skills": random.sample(fam["skills"], min(3, len(fam["skills"]))),
                })

        # Bổ sung 8 điểm ngoại lai / tin rác trôi dạt (Isolation Forest Anomaly)
        for i in range(8):
            idx += 1
            points.append({
                "id": f"anomaly_{idx}",
                "title": "Tuyển Dụng Làm Việc Tại Nhà Thu Nhập Khủng",
                "company": "Tập Đoàn Đa Quốc Gia Ảo",
                "job_family": "SPAM / UNKNOWN",
                "salary_vnd": 120.0,
                "x": round(random.choice([-6.0, 6.0]) + random.gauss(0, 0.5), 3),
                "y": round(random.choice([-6.0, 6.0]) + random.gauss(0, 0.5), 3),
                "z": round(random.choice([-6.0, 6.0]) + random.gauss(0, 0.5), 3),
                "is_anomaly": True,
                "skills": ["Gõ văn bản", "Đăng bài", "Không cần kinh nghiệm"],
            })

        return {
            "algorithm": "umap_3d",
            "total_points": len(points),
            "points": points,
            "cluster_centers": [
                {"name": f["name"], "x": f["center"][0], "y": f["center"][1], "z": f["center"][2]}
                for f in families
            ],
        }

    def get_isolation_forest_3d(self) -> Dict[str, Any]:
        """Sinh dữ liệu ranh giới mặt cong phân tách tin rác 3D."""
        base = self.get_umap_3d_clusters(sample_size=120)

        # Lưới tọa độ bề mặt phân tách (Decision Surface Mesh)
        # Bề mặt cong phân tách vùng tin thật vs vùng tin rác
        mesh_x = []
        mesh_y = []
        mesh_z = []

        grid_steps = 10
        for i in range(grid_steps):
            u = -4.0 + (8.0 * i / (grid_steps - 1))
            row_x, row_y, row_z = [], [], []
            for j in range(grid_steps):
                v = -4.0 + (8.0 * j / (grid_steps - 1))
                # Mặt cong paraboloid biểu diễn decision boundary
                w = round(4.5 - (u**2 + v**2) / 8.0, 3)
                row_x.append(round(u, 2))
                row_y.append(round(v, 2))
                row_z.append(w)
            mesh_x.append(row_x)
            mesh_y.append(row_y)
            mesh_z.append(row_z)

        return {
            "algorithm": "isolation_forest_3d",
            "total_points": base["total_points"],
            "points": base["points"],
            "decision_boundary_mesh": {
                "x": mesh_x,
                "y": mesh_y,
                "z": mesh_z,
                "threshold_score": -0.15,
            },
        }


ml_spatial_3d_service = MLSpatial3DService()
