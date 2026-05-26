#!/usr/bin/env python3
"""
image_to_mujoco_v4.py
=====================
Convierte un PNG/JPG/BMP/TIFF/PDF en un mundo XML para MuJoCo
con flujo completo:

  1. Carga imagen
  2. Detecta líneas negras → paredes (Hough + componentes conectados + RANSAC)
  3. Calibración px/m con dos puntos (GUI Tkinter)
  4. Editor 2D: ver/añadir/eliminar paredes con zoom+pan fluido
  5. Preview 3D en ventana OpenGL (PyOpenGL + pygame) — sin crashes de memoria
  6. Exportación a XML MuJoCo (fragmento <include> o escena completa)

Uso:
    python3 image_to_mujoco_v4.py plano.png
    python3 image_to_mujoco_v4.py plano.png --ppm 100 --standalone --output scene.xml

Dependencias:
    pip install opencv-python numpy Pillow
    pip install pygame PyOpenGL PyOpenGL-accelerate   # para preview 3D (opcional)
    pip install pdf2image                              # solo para PDF
    sudo apt install poppler-utils python3-tk
"""

# ──────────────────────────────────────────────────────────────────────────────
import argparse
import math
import sys
import threading
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

try:
    from PIL import Image, ImageTk
except ImportError:
    sys.exit("ERROR: pip install Pillow")

# Preview 3D opcional
try:
    import pygame
    from pygame.locals import *
    from OpenGL.GL import *
    from OpenGL.GLU import *
    HAS_3D = True
except ImportError:
    HAS_3D = False


# ══════════════════════════════════════════════════════════════════════════════
# Geometría
# ══════════════════════════════════════════════════════════════════════════════

class Wall:
    __slots__ = ("cx", "cy", "length", "thickness", "angle_deg", "selected", "source")

    def __init__(self, cx, cy, length, thickness, angle_deg, source="unknown"):
        self.cx = float(cx)
        self.cy = float(cy)
        self.length = float(max(length, 1.0))
        self.thickness = float(max(thickness, 1.0))
        self.angle_deg = float(angle_deg)
        self.selected = False
        self.source = source

    def normalized_angle(self) -> float:
        return self.angle_deg % 180.0

    def direction(self) -> Tuple[float, float]:
        a = math.radians(self.angle_deg)
        return math.cos(a), math.sin(a)

    def endpoints_px(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        ux, uy = self.direction()
        hl = self.length / 2.0
        return (self.cx - ux * hl, self.cy - uy * hl), (self.cx + ux * hl, self.cy + uy * hl)

    def corners_px(self) -> np.ndarray:
        rect = ((self.cx, self.cy), (self.length, self.thickness), self.angle_deg)
        return cv2.boxPoints(rect)

    def bbox_px(self) -> Tuple[float, float, float, float]:
        pts = self.corners_px()
        return float(np.min(pts[:, 0])), float(np.min(pts[:, 1])), \
               float(np.max(pts[:, 0])), float(np.max(pts[:, 1]))

    def distance_to_point_sq(self, px: float, py: float) -> float:
        (x1, y1), (x2, y2) = self.endpoints_px()
        vx, vy = x2 - x1, y2 - y1
        wx, wy = px - x1, py - y1
        c1 = vx * wx + vy * wy
        if c1 <= 0:
            return (px - x1) ** 2 + (py - y1) ** 2
        c2 = vx * vx + vy * vy
        if c2 <= c1:
            return (px - x2) ** 2 + (py - y2) ** 2
        b = c1 / c2
        bx, by = x1 + b * vx, y1 + b * vy
        return (px - bx) ** 2 + (py - by) ** 2

    def to_mjcf(self, name: str, ppm: float, origin_px: Tuple[float, float],
                h_m: float, t_m: float, group: int, material: str) -> str:
        ox, oy = origin_px
        x_m = (self.cx - ox) / ppm
        y_m = -(self.cy - oy) / ppm
        z_m = h_m / 2.0
        lm = self.length / ppm
        return (
            f'    <geom name="{name}" type="box" group="{group}" '
            f'pos="{x_m:.4f} {y_m:.4f} {z_m:.4f}" '
            f'size="{lm/2:.4f} {t_m/2:.4f} {h_m/2:.4f}" '
            f'euler="0 0 {-self.angle_deg:.2f}" '
            f'material="{material}" friction="1 0.05 0.01"/>'
        )


# ══════════════════════════════════════════════════════════════════════════════
# Carga de imagen (PNG/JPG/BMP/TIFF/PDF)
# ══════════════════════════════════════════════════════════════════════════════

def load_input(path: Path, pdf_dpi: int = 300) -> np.ndarray:
    s = path.suffix.lower()
    if s in (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"):
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            raise RuntimeError(f"No pude abrir: {path}")
        return img
    if s == ".pdf":
        try:
            from pdf2image import convert_from_path
        except ImportError:
            raise RuntimeError("pip install pdf2image && sudo apt install poppler-utils")
        pages = convert_from_path(str(path), dpi=pdf_dpi, first_page=1, last_page=1)
        if not pages:
            raise RuntimeError("PDF vacío")
        return cv2.cvtColor(np.array(pages[0]), cv2.COLOR_RGB2BGR)
    raise RuntimeError(f"Formato no soportado: {s}")


# ══════════════════════════════════════════════════════════════════════════════
# Pre-procesado: máscara de píxeles negros
# ══════════════════════════════════════════════════════════════════════════════

def build_wall_mask(
    img_bgr: np.ndarray,
    blur: int = 3,
    dark_thresh: int = 80,
    closing: int = 3,
    invert: bool = False,
) -> np.ndarray:
    """
    Devuelve una imagen binaria (255 = pared) robusta ante ruido y JPEG.
    Combina tres pistas: Otsu invertido, canal V de HSV y canal L de LAB.
    """
    # Opcionalmente invertir (plano blanco sobre negro)
    work = img_bgr if not invert else cv2.bitwise_not(img_bgr)

    gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
    if blur > 1:
        k = blur if blur % 2 == 1 else blur + 1
        gray = cv2.GaussianBlur(gray, (k, k), 0)

    # Pista 1: umbral adaptativo global (Otsu)
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

    # Pista 2: oscuridad absoluta por canal Value HSV
    v = cv2.split(cv2.cvtColor(work, cv2.COLOR_BGR2HSV))[2]
    dark_v = (v <= dark_thresh).astype(np.uint8) * 255

    # Pista 3: oscuridad en espacio LAB (canal L)
    lab_l = cv2.split(cv2.cvtColor(work, cv2.COLOR_BGR2LAB))[0]
    dark_l = (lab_l <= dark_thresh).astype(np.uint8) * 255

    # Unión de las tres pistas
    mask = cv2.bitwise_or(otsu, dark_v)
    mask = cv2.bitwise_or(mask, dark_l)

    # Eliminar ruido puntual (opening 3×3)
    k3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k3)

    # Cierre morfológico para cerrar huecos en paredes
    if closing > 0:
        kc = closing if closing % 2 == 1 else closing + 1
        ks = cv2.getStructuringElement(cv2.MORPH_RECT, (kc, kc))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, ks)

    return mask


# ══════════════════════════════════════════════════════════════════════════════
# Filtro de texto (componentes pequeños que no son pared)
# ══════════════════════════════════════════════════════════════════════════════

def remove_text_noise(
    mask: np.ndarray,
    max_area: int = 1200,
    max_aspect: float = 5.0,
    min_wall_dim: int = 40,
) -> Tuple[np.ndarray, int]:
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    out = np.zeros_like(mask)
    kept = 0
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        mx = max(w, h)
        mn = max(min(w, h), 1)
        aspect = mx / mn
        # Conservar si es grande, o muy alargado (parece pared), o largo en px
        if mx >= min_wall_dim or area >= max_area or aspect >= max_aspect:
            out[labels == i] = 255
            kept += 1
    return out, kept


# ══════════════════════════════════════════════════════════════════════════════
# Detección de paredes: Hough + Componentes conectados
# ══════════════════════════════════════════════════════════════════════════════

def angle_diff(a: float, b: float) -> float:
    d = abs((a % 180) - (b % 180))
    return min(d, 180 - d)


def detect_hough(
    mask: np.ndarray,
    min_len: int = 30,
    max_gap: int = 15,
    threshold: int = 25,
) -> List[Wall]:
    edges = cv2.Canny(mask, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold,
                             minLineLength=min_len, maxLineGap=max_gap)
    walls: List[Wall] = []
    if lines is None:
        return walls
    for ln in lines[:, 0, :]:
        x1, y1, x2, y2 = map(float, ln)
        length = math.hypot(x2 - x1, y2 - y1)
        if length < min_len:
            continue
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
        walls.append(Wall(cx, cy, length, 4.0, angle, "hough"))
    return walls


def detect_components(
    mask: np.ndarray,
    min_area: int = 80,
    min_len: int = 25,
    max_thick: int = 100,
) -> List[Wall]:
    num, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    walls: List[Wall] = []
    for i in range(1, num):
        x, y, w, h, area = stats[i]
        if area < min_area:
            continue
        m = np.uint8(labels == i) * 255
        pts = cv2.findNonZero(m)
        if pts is None or len(pts) < 5:
            continue
        rect = cv2.minAreaRect(pts)
        (cx, cy), (rw, rh), angle = rect
        length = max(rw, rh)
        thick  = max(1.0, min(rw, rh))
        if length < min_len or thick > max_thick:
            continue
        if rw < rh:
            angle += 90.0
        walls.append(Wall(cx, cy, length, thick, angle, "cc"))
    return walls


# ══════════════════════════════════════════════════════════════════════════════
# Fusión de segmentos colineales
# ══════════════════════════════════════════════════════════════════════════════

def _wall_params(w: Wall):
    ang = math.radians(w.normalized_angle())
    ux, uy = math.cos(ang), math.sin(ang)
    nx, ny = -uy, ux
    d = nx * w.cx + ny * w.cy
    return ang, d, (ux, uy), (nx, ny)


def merge_colinear(
    walls: List[Wall],
    dist_tol: float = 10.0,
    angle_tol: float = 5.0,
    gap_tol: float = 25.0,
) -> List[Wall]:
    if not walls:
        return []
    used = [False] * len(walls)
    merged: List[Wall] = []

    for i, wi in enumerate(walls):
        if used[i]:
            continue
        used[i] = True
        cluster = [wi]
        changed = True
        while changed:
            changed = False
            ref = _cluster_to_wall(cluster)
            _, d_ref, (ux, uy), _ = _wall_params(ref)
            projs_ref = []
            for w in cluster:
                (x1, y1), (x2, y2) = w.endpoints_px()
                projs_ref += [x1 * ux + y1 * uy, x2 * ux + y2 * uy]
            pmin, pmax = min(projs_ref), max(projs_ref)
            for j, wj in enumerate(walls):
                if used[j]:
                    continue
                if angle_diff(ref.angle_deg, wj.angle_deg) > angle_tol:
                    continue
                _, d_j, _, _ = _wall_params(wj)
                if abs(d_ref - d_j) > dist_tol:
                    continue
                eps = [p[0] * ux + p[1] * uy for p in wj.endpoints_px()]
                qmin, qmax = min(eps), max(eps)
                if qmin <= pmax + gap_tol and qmax >= pmin - gap_tol:
                    cluster.append(wj)
                    used[j] = True
                    changed = True
        merged.append(_cluster_to_wall(cluster))
    return merged


def _cluster_to_wall(cluster: List[Wall]) -> Wall:
    if len(cluster) == 1:
        c = cluster[0]
        return Wall(c.cx, c.cy, c.length, c.thickness, c.angle_deg, c.source)
    angles = np.array([w.normalized_angle() for w in cluster], dtype=np.float64)
    rad = np.deg2rad(angles)
    mean_ang = math.degrees(math.atan2(np.mean(np.sin(rad)), np.mean(np.cos(rad)))) % 180.0
    ux, uy = math.cos(math.radians(mean_ang)), math.sin(math.radians(mean_ang))
    nx, ny = -uy, ux
    points: List[Tuple[float, float]] = []
    thicknesses: List[float] = []
    for w in cluster:
        points.extend(w.endpoints_px())
        thicknesses.append(w.thickness)
    projs = [x * ux + y * uy for x, y in points]
    norms = [x * nx + y * ny for x, y in points]
    pmin, pmax = min(projs), max(projs)
    dmean = float(np.mean(norms))
    cx = (pmin + pmax) / 2 * ux + dmean * nx
    cy = (pmin + pmax) / 2 * uy + dmean * ny
    return Wall(cx, cy, pmax - pmin, float(np.median(thicknesses)), mean_ang, "merged")


# ══════════════════════════════════════════════════════════════════════════════
# Filtro de orientación dominante
# ══════════════════════════════════════════════════════════════════════════════

def filter_dominant_orientation(walls: List[Wall], tol: float = 12.0) -> List[Wall]:
    if len(walls) < 8:
        return walls
    angles = [w.normalized_angle() for w in walls]
    bins = Counter(int(a // 5) for a in angles)
    peaks = [b * 5 + 2.5 for b, _ in bins.most_common(2)]
    candidates = peaks + [(a + 90.0) % 180.0 for a in peaks]
    out = [w for w in walls if any(angle_diff(w.normalized_angle(), a) <= tol for a in candidates)]
    print(f"  Filtro orientación: {len(walls)} → {len(out)}")
    return out


# ══════════════════════════════════════════════════════════════════════════════
# Calibración GUI
# ══════════════════════════════════════════════════════════════════════════════

class CalibrationDialog:
    """
    Ventana Tkinter para marcar dos puntos e introducir la distancia real.
    Devuelve píxeles/metro.
    """

    def __init__(self, img_bgr: np.ndarray):
        self.img_bgr = img_bgr
        self.ppm: Optional[float] = None
        self._points: List[Tuple[int, int]] = []

        self.root = tk.Tk()
        self.root.title("Calibración — marca 2 puntos de distancia conocida")
        self.root.configure(bg="#111")

        h, w = img_bgr.shape[:2]
        sw = self.root.winfo_screenwidth() - 80
        sh = self.root.winfo_screenheight() - 160
        self.fit = min(sw / w, sh / h, 1.0)
        cw, ch = max(int(w * self.fit), 300), max(int(h * self.fit), 200)

        banner = tk.Label(
            self.root, bg="#111", fg="#afd7ff",
            font=("Courier", 11),
            text="LMB: marcar punto  |  Rueda: zoom  |  RMB/MMB: pan  |  R: reset  |  Esc: cancelar",
        )
        banner.pack(fill=tk.X, padx=6, pady=4)

        self.canvas = tk.Canvas(self.root, width=cw, height=ch, bg="#1a1a1a",
                                cursor="crosshair", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.status = tk.Label(self.root, bg="#111", fg="#88cc88",
                               font=("Courier", 10), text="Marca el primer punto")
        self.status.pack(fill=tk.X, padx=6, pady=4)

        self.zoom = self.fit
        self.ox, self.oy = 0.0, 0.0
        self._np_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)  # fuente numpy siempre en RAM
        self._tk_img = None  # referencia viva para Tkinter
        self._last_tile_key = None  # evita redibujado si nada cambió

        self._bind()
        self._redraw()

    def _bind(self):
        c = self.canvas
        c.bind("<ButtonPress-1>", self._lclick)
        c.bind("<ButtonPress-2>", self._pstart); c.bind("<B2-Motion>", self._pmove)
        c.bind("<ButtonPress-3>", self._pstart); c.bind("<B3-Motion>", self._pmove)
        c.bind("<MouseWheel>", self._zoom); c.bind("<Button-4>", self._zoom); c.bind("<Button-5>", self._zoom)
        self.root.bind("r", lambda e: self._reset()); self.root.bind("R", lambda e: self._reset())
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    def _i2s(self, ix, iy): return ix * self.zoom + self.ox, iy * self.zoom + self.oy
    def _s2i(self, sx, sy): return (sx - self.ox) / self.zoom, (sy - self.oy) / self.zoom

    def _tile(self):
        """
        Recorta SOLO el área visible del canvas en coordenadas de imagen,
        la escala al tamaño del canvas y devuelve un PhotoImage.
        Coste: O(canvas_w × canvas_h) en vez de O(img_w × img_h × zoom²).
        """
        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        ih, iw = self._np_rgb.shape[:2]

        # Esquinas del canvas en coordenadas de imagen (float)
        x0f, y0f = self._s2i(0,  0)
        x1f, y1f = self._s2i(cw, ch)

        # Clamp a los bordes de la imagen
        xi0 = max(0, int(math.floor(x0f)))
        yi0 = max(0, int(math.floor(y0f)))
        xi1 = min(iw, int(math.ceil(x1f)))
        yi1 = min(ih, int(math.ceil(y1f)))

        if xi1 <= xi0 or yi1 <= yi0:
            # Fuera de imagen: lienzo vacío
            blank = Image.new("RGB", (cw, ch), (26, 26, 26))
            self._tk_img = ImageTk.PhotoImage(blank)
            return self._tk_img, 0, 0

        # Crop numpy (vista, sin copia si es posible)
        crop = self._np_rgb[yi0:yi1, xi0:xi1]

        # Tamaño de destino en pantalla para este crop
        dst_w = int(round((xi1 - xi0) * self.zoom))
        dst_h = int(round((yi1 - yi0) * self.zoom))
        dst_w = max(1, min(dst_w, cw + 4))
        dst_h = max(1, min(dst_h, ch + 4))

        # Elegir interpolación: INTER_NEAREST para zoom grande (rápido y nítido),
        # INTER_AREA para zoom pequeño (antialias barato)
        interp = cv2.INTER_NEAREST if self.zoom >= 1.0 else cv2.INTER_AREA
        scaled_np = cv2.resize(crop, (dst_w, dst_h), interpolation=interp)

        pil_tile = Image.fromarray(scaled_np)
        self._tk_img = ImageTk.PhotoImage(pil_tile)

        # Offset en pantalla donde empieza este tile
        sx0 = int(round(xi0 * self.zoom + self.ox))
        sy0 = int(round(yi0 * self.zoom + self.oy))
        return self._tk_img, sx0, sy0

    def _redraw(self):
        self.canvas.delete("all")
        tk_img, sx0, sy0 = self._tile()
        self.canvas.create_image(sx0, sy0, image=tk_img, anchor=tk.NW)
        for idx, (px, py) in enumerate(self._points):
            sx, sy = self._i2s(px, py)
            r = 6
            self.canvas.create_oval(sx-r, sy-r, sx+r, sy+r, fill="#ff4444", outline="white", width=2)
            self.canvas.create_text(sx+10, sy-10, text=f"P{idx+1}", fill="white",
                                    font=("Courier", 10, "bold"))
        if len(self._points) == 2:
            sx1, sy1 = self._i2s(*self._points[0])
            sx2, sy2 = self._i2s(*self._points[1])
            self.canvas.create_line(sx1, sy1, sx2, sy2, fill="#ffdd44", width=2, dash=(6, 3))

    def _lclick(self, e):
        if len(self._points) >= 2:
            self._points.clear()
        ix, iy = self._s2i(e.x, e.y)
        self._points.append((int(ix), int(iy)))
        self._redraw()
        if len(self._points) == 1:
            self.status.config(text="Marca el segundo punto")
        elif len(self._points) == 2:
            self.status.config(text="Dos puntos marcados — introduce la distancia")
            self._ask_distance()

    def _ask_distance(self):
        (x1, y1), (x2, y2) = self._points
        px_dist = math.hypot(x2 - x1, y2 - y1)
        d = simpledialog.askfloat(
            "Distancia real", f"Distancia entre los dos puntos en metros:\n(separación en píxeles: {px_dist:.1f} px)",
            parent=self.root, minvalue=0.01)
        if d and d > 0:
            self.ppm = px_dist / d
            self.status.config(text=f"✓ Escala: {self.ppm:.2f} px/m  (cierra la ventana para continuar)")
            self.root.title(f"Calibración — {self.ppm:.2f} px/m — CERRAR para continuar")
            ok_btn = tk.Button(self.root, text="✓  Confirmar y continuar",
                               bg="#1e6633", fg="white", font=("Courier", 12, "bold"),
                               command=self.root.destroy)
            ok_btn.pack(pady=6, fill=tk.X, padx=40)
        else:
            self._points.clear()
            self.status.config(text="Distancia cancelada — marca de nuevo")
            self._redraw()

    def _pstart(self, e): self._ps = (e.x, e.y, self.ox, self.oy)
    def _pmove(self, e):
        if not hasattr(self, "_ps"): return
        self.ox = self._ps[2] + e.x - self._ps[0]
        self.oy = self._ps[3] + e.y - self._ps[1]
        self._redraw()

    def _zoom(self, e):
        f = (1.15 if (getattr(e, "delta", 0) > 0 or getattr(e, "num", None) == 4) else 1/1.15)
        nz = max(0.05, min(40.0, self.zoom * f))
        ix, iy = self._s2i(e.x, e.y)
        self.zoom = nz
        self.ox = e.x - ix * nz
        self.oy = e.y - iy * nz
        # Throttle: cancelar redibujado pendiente y programar uno nuevo en 30ms
        if hasattr(self, '_zoom_after') and self._zoom_after:
            self.root.after_cancel(self._zoom_after)
        self._zoom_after = self.root.after(30, self._redraw)

    def _reset(self):
        self.zoom = self.fit; self.ox = self.oy = 0.0
        self._points.clear(); self._redraw()
        self.status.config(text="Marca el primer punto")

    def run(self) -> Optional[float]:
        self.root.mainloop()
        return self.ppm


# ══════════════════════════════════════════════════════════════════════════════
# Editor 2D de paredes
# ══════════════════════════════════════════════════════════════════════════════

class WallEditor:
    """
    Editor Tkinter de paredes con:
    - Zoom + pan fluidos (tile renderer — siempre O(canvas) en coste)
    - Culling por viewport
    - Selección individual (clic) y por área (drag)
    - Añadir paredes dibujando una línea  (W)
    - Eliminar paredes seleccionadas      (D / Delete)
    - Redetectar zona seleccionada        (E) — recorta la máscara en el
      rectángulo dibujado, corre el pipeline completo y añade las paredes
      nuevas con el offset correcto en coordenadas de imagen
    - Toggle todas las paredes            (A)
    - Undo                                (Z)
    """

    def __init__(self, img_bgr: np.ndarray, walls: List[Wall],
                 mask: Optional[np.ndarray] = None,
                 detect_params: Optional[dict] = None):
        self.img_bgr = img_bgr
        self.walls: List[Wall] = [Wall(w.cx, w.cy, w.length, w.thickness,
                                       w.angle_deg, w.source) for w in walls]
        # Máscara binaria y parámetros de detección para redetectar zonas
        self._mask: Optional[np.ndarray] = mask
        self._dparams: dict = detect_params or {}

        self.saved = False
        self._mode = "select"   # "select" | "add" | "redetect"
        self._add_pt1: Optional[Tuple[float, float]] = None
        self._rdet_pt1: Optional[Tuple[float, float]] = None

        self.root = tk.Tk()
        self.root.title("Editor de paredes — Guardar (S) para exportar")
        self.root.configure(bg="#111")

        # ── Toolbar ──────────────────────────────────────────────────────────
        tb = tk.Frame(self.root, bg="#1a1a1a")
        tb.pack(fill=tk.X)
        btns = [
            ("Seleccionar (Q)", "#2a4a2a", self._mode_select),
            ("Añadir pared (W)", "#2a2a4a", self._mode_add),
            ("Redetectar zona (E)", "#2a3a4a", self._mode_redetect),
            ("Eliminar sel. (D)", "#4a2a2a", self._delete_selected),
            ("Sel. todo (A)", "#444", self._toggle_all),
            ("Reset zoom (R)", "#333", self._reset_zoom),
            ("⟵ Atrás (Z)", "#333", self._undo),
            ("✔ Guardar (S)", "#1e6633", self._save),
            ("✘ Cancelar (Esc)", "#661e1e", self._cancel),
        ]
        self._btn_refs: dict = {}
        for label, color, cmd in btns:
            b = tk.Button(tb, text=label, bg=color, fg="white",
                          font=("Courier", 9, "bold"), command=cmd,
                          relief=tk.FLAT, padx=8, pady=4)
            b.pack(side=tk.LEFT, padx=2, pady=4)
            self._btn_refs[label] = b

        # ── Canvas ────────────────────────────────────────────────────────────
        h, w = img_bgr.shape[:2]
        sw = self.root.winfo_screenwidth() - 60
        sh = self.root.winfo_screenheight() - 180
        self.fit = min(sw / w, sh / h, 1.0)
        cw, ch = max(int(w * self.fit), 400), max(int(h * self.fit), 300)

        self.canvas = tk.Canvas(self.root, width=cw, height=ch,
                                bg="#1a1a1a", cursor="crosshair", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.status = tk.Label(self.root, bg="#111", fg="#88cc88",
                               font=("Courier", 10),
                               text="LMB: seleccionar | D: eliminar | W: añadir | S: guardar")
        self.status.pack(fill=tk.X, padx=6, pady=4)

        # ── Estado ────────────────────────────────────────────────────────────
        self.zoom = self.fit
        self.ox, self.oy = 0.0, 0.0
        self._np_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        self._tk_img = None
        self._drag_start: Optional[Tuple[int, int]] = None
        self._drag_rect = None
        self._sel_all = False
        self._undo_stack: List[List[Wall]] = []

        self._bind()
        self._redraw()

    # ── Utilerias coord ───────────────────────────────────────────────────────
    def _i2s(self, ix, iy): return ix * self.zoom + self.ox, iy * self.zoom + self.oy
    def _s2i(self, sx, sy): return (sx - self.ox) / self.zoom, (sy - self.oy) / self.zoom

    # ── Tile renderer: solo escala el área visible ────────────────────────────
    def _tile(self):
        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        ih, iw = self._np_rgb.shape[:2]
        x0f, y0f = self._s2i(0,  0)
        x1f, y1f = self._s2i(cw, ch)
        xi0 = max(0, int(math.floor(x0f)))
        yi0 = max(0, int(math.floor(y0f)))
        xi1 = min(iw, int(math.ceil(x1f)))
        yi1 = min(ih, int(math.ceil(y1f)))
        if xi1 <= xi0 or yi1 <= yi0:
            blank = Image.new("RGB", (cw, ch), (26, 26, 26))
            self._tk_img = ImageTk.PhotoImage(blank)
            return self._tk_img, 0, 0
        crop = self._np_rgb[yi0:yi1, xi0:xi1]
        dst_w = max(1, min(int(round((xi1-xi0)*self.zoom)), cw+4))
        dst_h = max(1, min(int(round((yi1-yi0)*self.zoom)), ch+4))
        interp = cv2.INTER_NEAREST if self.zoom >= 1.0 else cv2.INTER_AREA
        self._tk_img = ImageTk.PhotoImage(Image.fromarray(
            cv2.resize(crop, (dst_w, dst_h), interpolation=interp)))
        sx0 = int(round(xi0 * self.zoom + self.ox))
        sy0 = int(round(yi0 * self.zoom + self.oy))
        return self._tk_img, sx0, sy0

    # ── Dibujo ────────────────────────────────────────────────────────────────
    def _visible(self, w: Wall, m=40.0) -> bool:
        x0, y0, x1, y1 = w.bbox_px()
        sx0, sy0 = self._i2s(x0, y0); sx1, sy1 = self._i2s(x1, y1)
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        return not (sx1 < -m or sx0 > cw + m or sy1 < -m or sy0 > ch + m)

    def _redraw(self):
        self.canvas.delete("wall", "img", "status_over")
        tk_img, sx0, sy0 = self._tile()
        self.canvas.create_image(sx0, sy0, image=tk_img, anchor=tk.NW, tags="img")
        n_vis = 0
        for w in self.walls:
            if not self._visible(w): continue
            (x1, y1), (x2, y2) = w.endpoints_px()
            sx1, sy1 = self._i2s(x1, y1); sx2, sy2 = self._i2s(x2, y2)
            color = "#ff3355" if w.selected else "#00e676"
            width = 4 if w.selected else 2
            self.canvas.create_line(sx1, sy1, sx2, sy2,
                                    fill=color, width=width, tags="wall")
            n_vis += 1
        n_sel = sum(1 for w in self.walls if w.selected)
        mode_labels = {
            "select":    "[ SELECCIONAR  Q ]",
            "add":       "[ AÑADIR PARED  W ]",
            "redetect":  "[ REDETECTAR ZONA  E — arrastra un rectángulo ]",
        }
        mode_txt = mode_labels.get(self._mode, self._mode)
        has_mask = "  ✓ máscara" if self._mask is not None else "  ✗ sin máscara"
        self.status.config(
            text=f"{mode_txt}  |  Paredes: {len(self.walls)} vis:{n_vis} sel:{n_sel} zoom:{self.zoom:.2f}x{has_mask}")

    # ── Bind eventos ─────────────────────────────────────────────────────────
    def _bind(self):
        c = self.canvas
        c.bind("<ButtonPress-1>", self._lpress)
        c.bind("<B1-Motion>",     self._ldrag)
        c.bind("<ButtonRelease-1>", self._lrel)
        c.bind("<ButtonPress-2>",  self._pstart); c.bind("<B2-Motion>", self._pmove)
        c.bind("<ButtonPress-3>",  self._pstart); c.bind("<B3-Motion>", self._pmove)
        c.bind("<MouseWheel>",  self._zoom); c.bind("<Button-4>", self._zoom); c.bind("<Button-5>", self._zoom)
        for k in ("d", "D", "<Delete>"):
            self.root.bind(k, lambda e: self._delete_selected())
        for k in ("a", "A"):
            self.root.bind(k, lambda e: self._toggle_all())
        for k in ("s", "S"):
            self.root.bind(k, lambda e: self._save())
        for k in ("r", "R"):
            self.root.bind(k, lambda e: self._reset_zoom())
        for k in ("q", "Q"):
            self.root.bind(k, lambda e: self._mode_select())
        for k in ("w", "W"):
            self.root.bind(k, lambda e: self._mode_add())
        for k in ("e", "E"):
            self.root.bind(k, lambda e: self._mode_redetect())
        for k in ("z", "Z"):
            self.root.bind(k, lambda e: self._undo())
        self.root.bind("<Escape>", lambda e: self._cancel())

    # ── Modos ─────────────────────────────────────────────────────────────────
    def _mode_select(self):
        self._mode = "select"; self._add_pt1 = None; self._rdet_pt1 = None
        self.canvas.config(cursor="crosshair"); self._redraw()

    def _mode_add(self):
        self._mode = "add"; self._add_pt1 = None; self._rdet_pt1 = None
        self.canvas.config(cursor="tcross"); self._redraw()

    def _mode_redetect(self):
        if self._mask is None:
            self.status.config(text="⚠ No hay máscara disponible para redetectar")
            return
        self._mode = "redetect"; self._rdet_pt1 = None; self._add_pt1 = None
        self.canvas.config(cursor="sizing"); self._redraw()

    # ── Interacción ──────────────────────────────────────────────────────────
    def _lpress(self, e):
        if self._mode == "add":
            ix, iy = self._s2i(e.x, e.y)
            if self._add_pt1 is None:
                self._add_pt1 = (ix, iy)
                self.status.config(text="Clic para fijar el segundo extremo de la pared")
            else:
                self._push_undo()
                x1, y1 = self._add_pt1
                x2, y2 = ix, iy
                length = math.hypot(x2 - x1, y2 - y1)
                if length > 5:
                    cx, cy = (x1+x2)/2, (y1+y2)/2
                    angle = math.degrees(math.atan2(y2-y1, x2-x1))
                    self.walls.append(Wall(cx, cy, length, 4.0, angle, "manual"))
                self._add_pt1 = None
                self._redraw()
        elif self._mode == "redetect":
            self._drag_start = (e.x, e.y)
        else:
            self._drag_start = (e.x, e.y)

    def _ldrag(self, e):
        if self._drag_start is None: return
        x0, y0 = self._drag_start
        if abs(e.x-x0) < 4 and abs(e.y-y0) < 4: return
        if self._drag_rect: self.canvas.delete(self._drag_rect)
        color = "#ff9900" if self._mode == "redetect" else "#44aaff"
        self._drag_rect = self.canvas.create_rectangle(
            x0, y0, e.x, e.y, outline=color, width=2, dash=(4, 2))

    def _lrel(self, e):
        if self._drag_start is None: return
        x0, y0 = self._drag_start
        dx, dy = abs(e.x-x0), abs(e.y-y0)
        if self._drag_rect: self.canvas.delete(self._drag_rect); self._drag_rect = None

        if self._mode == "redetect":
            if dx >= 8 and dy >= 8:
                ix0, iy0 = self._s2i(min(x0,e.x), min(y0,e.y))
                ix1, iy1 = self._s2i(max(x0,e.x), max(y0,e.y))
                self._redetect_zone(ix0, iy0, ix1, iy1)
            self._drag_start = None
            return

        if dx < 4 and dy < 4:
            self._click_select(e.x, e.y)
        else:
            ix0, iy0 = self._s2i(min(x0,e.x), min(y0,e.y))
            ix1, iy1 = self._s2i(max(x0,e.x), max(y0,e.y))
            for w in self.walls:
                if ix0 <= w.cx <= ix1 and iy0 <= w.cy <= iy1:
                    w.selected = True
        self._drag_start = None
        self._redraw()

    def _redetect_zone(self, ix0: float, iy0: float, ix1: float, iy1: float):
        """
        Recorta la máscara en el rectángulo [ix0,iy0,ix1,iy1] (coords imagen),
        corre el pipeline de detección completo en esa región, y añade las
        paredes resultantes al listado global con el offset correcto.
        Las paredes cuyo centro caiga dentro del rectángulo se eliminan primero.
        """
        if self._mask is None:
            return
        ih, iw = self._mask.shape[:2]
        xi0 = max(0, int(math.floor(ix0)))
        yi0 = max(0, int(math.floor(iy0)))
        xi1 = min(iw, int(math.ceil(ix1)))
        yi1 = min(ih, int(math.ceil(iy1)))
        if xi1 - xi0 < 10 or yi1 - yi0 < 10:
            self.status.config(text="⚠ Zona demasiado pequeña para redetectar")
            return

        self.status.config(text="⏳ Redetectando zona…")
        self.root.update_idletasks()

        # Guardar undo antes de modificar
        self._push_undo()

        # Eliminar paredes cuyo centro esté dentro del rectángulo
        self.walls[:] = [w for w in self.walls
                         if not (xi0 <= w.cx <= xi1 and yi0 <= w.cy <= yi1)]

        # Recortar máscara y redetectar
        crop_mask = self._mask[yi0:yi1, xi0:xi1]
        p = self._dparams
        w_h = detect_hough(crop_mask,
                            p.get('min_line', 30),
                            p.get('max_gap', 15),
                            p.get('hough_thr', 25))
        w_c = detect_components(crop_mask)
        new_walls = merge_colinear(w_h + w_c, p.get('merge_dist', 10.0))
        new_walls = [w for w in new_walls
                     if w.length >= max(15.0, p.get('min_line', 30) * 0.5)]

        # Trasladar coordenadas al espacio de imagen completo
        for w in new_walls:
            w.cx += xi0
            w.cy += yi0
            w.source = "redetected"

        self.walls.extend(new_walls)
        n = len(new_walls)
        self.status.config(text=f"✓ Redetectadas {n} paredes en la zona")
        self._redraw()

    def _click_select(self, sx, sy):
        ix, iy = self._s2i(sx, sy)
        tol = (20.0 / max(self.zoom, 0.01)) ** 2
        best_i, best_d = -1, float("inf")
        for i, w in enumerate(self.walls):
            d = w.distance_to_point_sq(ix, iy)
            if d < best_d: best_d, best_i = d, i
        if best_i >= 0 and best_d <= tol:
            self.walls[best_i].selected = not self.walls[best_i].selected

    def _pstart(self, e): self._ps = (e.x, e.y, self.ox, self.oy)
    def _pmove(self, e):
        if not hasattr(self, "_ps"): return
        self.ox = self._ps[2] + e.x - self._ps[0]
        self.oy = self._ps[3] + e.y - self._ps[1]
        self._redraw()

    def _zoom(self, e):
        f = 1.15 if (getattr(e,"delta",0)>0 or getattr(e,"num",None)==4) else 1/1.15
        nz = max(0.05, min(40.0, self.zoom*f))
        ix, iy = self._s2i(e.x, e.y)
        self.zoom = nz; self.ox = e.x - ix*nz; self.oy = e.y - iy*nz
        # Throttle: 30ms tras el último evento de rueda
        if hasattr(self, '_zoom_after') and self._zoom_after:
            self.root.after_cancel(self._zoom_after)
        self._zoom_after = self.root.after(30, self._redraw)

    def _reset_zoom(self): self.zoom=self.fit; self.ox=self.oy=0.0; self._redraw()

    def _push_undo(self):
        snap = [Wall(w.cx, w.cy, w.length, w.thickness, w.angle_deg, w.source) for w in self.walls]
        self._undo_stack.append(snap)
        if len(self._undo_stack) > 30: self._undo_stack.pop(0)

    def _undo(self):
        if not self._undo_stack: return
        self.walls[:] = self._undo_stack.pop()
        self._redraw()

    def _delete_selected(self):
        self._push_undo()
        self.walls[:] = [w for w in self.walls if not w.selected]
        self._redraw()

    def _toggle_all(self):
        self._sel_all = not self._sel_all
        for w in self.walls: w.selected = self._sel_all
        self._redraw()

    def _save(self): self.saved=True; self.root.destroy()
    def _cancel(self):
        if messagebox.askyesno("Cancelar", "¿Salir sin guardar?", parent=self.root):
            self.saved=False; self.root.destroy()

    def run(self) -> bool:
        self.root.mainloop()
        return self.saved


# ══════════════════════════════════════════════════════════════════════════════
# Preview 3D con pygame + PyOpenGL
# ══════════════════════════════════════════════════════════════════════════════

def show_3d_preview(walls: List[Wall], ppm: float, img_w: int, img_h: int,
                     wall_h: float = 2.5, wall_t: float = 0.15) -> bool:
    """
    Abre una ventana OpenGL con preview 3D.
    Devuelve True si el usuario pulsa ENTER/ESPACIO para confirmar,
    False si pulsa Escape.
    Gestión cuidadosa de memoria: sin listas de display, sin texturas grandes.
    """
    if not HAS_3D:
        print("  [INFO] pygame/PyOpenGL no disponible → preview 3D omitida")
        return True

    pygame.init()
    display = (1280, 720)
    pygame.display.set_mode(display, DOUBLEBUF | OPENGL)
    pygame.display.set_caption("Preview 3D — ENTER: confirmar | ESC: cancelar | WASD+ratón: navegar")

    # Configuración OpenGL básica
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
    glLightfv(GL_LIGHT0, GL_POSITION, [0, 10, 10, 0])
    glLightfv(GL_LIGHT0, GL_DIFFUSE,  [0.9, 0.9, 0.9, 1.0])
    glLightfv(GL_LIGHT0, GL_AMBIENT,  [0.3, 0.3, 0.3, 1.0])
    glClearColor(0.12, 0.14, 0.18, 1.0)

    glMatrixMode(GL_PROJECTION)
    gluPerspective(60, display[0]/display[1], 0.1, 200.0)
    glMatrixMode(GL_MODELVIEW)

    # Escena: convertir paredes a metros
    ox, oy = img_w / 2.0, img_h / 2.0
    scene_walls = []
    for w in walls:
        xm = (w.cx - ox) / ppm
        ym = -(w.cy - oy) / ppm
        lm = w.length / ppm
        scene_walls.append((xm, ym, lm, wall_h, wall_t, w.angle_deg))

    max_extent = max((img_w, img_h)) / ppm
    cam_x, cam_y, cam_z = 0.0, -max_extent * 0.6, max_extent * 0.5
    yaw, pitch = 0.0, -25.0
    speed = 0.15
    mouse_captured = False
    clock = pygame.time.Clock()

    def draw_box(x, y, lm, h, t, angle_deg):
        glPushMatrix()
        glTranslatef(x, y, h / 2)
        glRotatef(-angle_deg, 0, 0, 1)
        # Escalar para hacer una caja
        glScalef(lm / 2, t / 2, h / 2)
        # Caja unitaria manual (evita numpy interno de glutSolidCube)
        v = [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
             (-1,-1, 1),(1,-1, 1),(1,1, 1),(-1,1, 1)]
        faces = [(0,1,2,3),(4,5,6,7),(0,1,5,4),
                 (2,3,7,6),(1,2,6,5),(0,3,7,4)]
        normals = [(0,0,-1),(0,0,1),(0,-1,0),(0,1,0),(1,0,0),(-1,0,0)]
        glBegin(GL_QUADS)
        for fi, face in enumerate(faces):
            glNormal3fv(normals[fi])
            for vi in face:
                glVertex3fv(v[vi])
        glEnd()
        glPopMatrix()

    def draw_grid(size=20, step=1):
        glDisable(GL_LIGHTING)
        glColor3f(0.25, 0.25, 0.3)
        glLineWidth(1.0)
        glBegin(GL_LINES)
        for i in range(-size, size+1, step):
            glVertex3f(i, -size, 0); glVertex3f(i, size, 0)
            glVertex3f(-size, i, 0); glVertex3f(size, i, 0)
        glEnd()
        glEnable(GL_LIGHTING)

    result = True

    while True:
        dt = clock.tick(60) / 1000.0
        for ev in pygame.event.get():
            if ev.type == QUIT:
                result = False; pygame.quit(); return result
            if ev.type == KEYDOWN:
                if ev.key == K_ESCAPE:
                    result = False; pygame.quit(); return result
                if ev.key in (K_RETURN, K_SPACE, K_KP_ENTER):
                    result = True; pygame.quit(); return result
                if ev.key == K_m:
                    mouse_captured = not mouse_captured
                    pygame.event.set_grab(mouse_captured)
                    pygame.mouse.set_visible(not mouse_captured)
            if ev.type == MOUSEBUTTONDOWN and ev.button == 1:
                mouse_captured = True
                pygame.event.set_grab(True); pygame.mouse.set_visible(False)
            if ev.type == MOUSEBUTTONUP and ev.button == 3:
                mouse_captured = False
                pygame.event.set_grab(False); pygame.mouse.set_visible(True)
            if ev.type == MOUSEMOTION and mouse_captured:
                yaw   += ev.rel[0] * 0.3
                pitch  = max(-89, min(89, pitch - ev.rel[1] * 0.3))

        keys = pygame.key.get_pressed()
        yr = math.radians(yaw)
        fwd = (math.sin(yr), math.cos(yr), 0.0)
        right = (math.cos(yr), -math.sin(yr), 0.0)
        if keys[K_w] or keys[K_UP]:    cam_x+=fwd[0]*speed; cam_y+=fwd[1]*speed
        if keys[K_s] or keys[K_DOWN]:  cam_x-=fwd[0]*speed; cam_y-=fwd[1]*speed
        if keys[K_a] or keys[K_LEFT]:  cam_x-=right[0]*speed; cam_y-=right[1]*speed
        if keys[K_d] or keys[K_RIGHT]: cam_x+=right[0]*speed; cam_y+=right[1]*speed
        if keys[K_q]: cam_z -= speed
        if keys[K_e]: cam_z += speed

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        pr = math.radians(pitch)
        lx = math.sin(yr) * math.cos(pr)
        ly = math.cos(yr) * math.cos(pr)
        lz = math.sin(pr)
        gluLookAt(cam_x, cam_y, cam_z,
                  cam_x+lx, cam_y+ly, cam_z+lz,
                  0, 0, 1)

        draw_grid()

        # Suelo
        glDisable(GL_LIGHTING)
        glColor4f(0.18, 0.18, 0.20, 1.0)
        glBegin(GL_QUADS)
        s = max_extent
        glVertex3f(-s,-s,0); glVertex3f(s,-s,0); glVertex3f(s,s,0); glVertex3f(-s,s,0)
        glEnd()
        glEnable(GL_LIGHTING)

        # Paredes
        glColor3f(0.65, 0.60, 0.55)
        for (xm, ym, lm, h, t, angle) in scene_walls:
            draw_box(xm, ym, lm, h, t, angle)

        pygame.display.flip()

    pygame.quit()
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Exportación MuJoCo XML
# ══════════════════════════════════════════════════════════════════════════════

def write_fragment(walls, path, ppm, origin_px, h_m, t_m, group, source, mat):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "<!--",
        "  image_to_mujoco_v4.py — fragmento de paredes",
        f"  Fuente: {source}",
        f"  Fecha: {ts}",
        f"  Paredes: {len(walls)} | escala: {ppm:.3f} px/m | altura: {h_m} m | grosor: {t_m} m",
        '  Uso: <include file="..."/> dentro de <worldbody>',
        "-->",
        '<body name="generated_walls">',
    ]
    for i, w in enumerate(walls):
        lines.append(w.to_mjcf(f"wall_{i:03d}", ppm, origin_px, h_m, t_m, group, mat))
    lines.append("</body>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_standalone(walls, path, ppm, origin_px, h_m, t_m, group, source, mat):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f'<mujoco model="generated_scene">',
        "  <!-- Generado por image_to_mujoco_v4.py",
        f"       Fuente: {source} | Fecha: {ts} -->",
        "  <visual>",
        '    <headlight diffuse="0.6 0.6 0.6" ambient="0.3 0.3 0.3" specular="0 0 0"/>',
        '    <rgba haze="0.15 0.25 0.35 1"/>',
        '    <global azimuth="-130" elevation="-20"/>',
        "  </visual>",
        "  <asset>",
        '    <texture type="skybox" builtin="gradient" rgb1="0.3 0.5 0.7" rgb2="0 0 0" width="512" height="3072"/>',
        '    <texture type="2d" name="groundplane" builtin="checker" mark="edge"',
        '             rgb1="0.22 0.22 0.22" rgb2="0.12 0.12 0.12"',
        '             markrgb="0.7 0.7 0.7" width="300" height="300"/>',
        '    <material name="groundplane" texture="groundplane" texuniform="true" texrepeat="5 5" reflectance="0.15"/>',
        f'    <material name="{mat}" rgba="0.55 0.50 0.45 1" reflectance="0.05"/>',
        "  </asset>",
        "  <worldbody>",
        '    <light pos="0 0 4"   dir="0 0 -1" directional="true" diffuse="0.7 0.7 0.7"/>',
        '    <light pos="3 3 4"   dir="0 0 -1" directional="true" diffuse="0.3 0.3 0.3"/>',
        '    <light pos="-3 -3 4" dir="0 0 -1" directional="true" diffuse="0.3 0.3 0.3"/>',
        '    <geom name="floor" type="plane" size="0 0 0.05" material="groundplane" friction="2.5 2.5 2.5" group="3"/>',
        '    <body name="generated_walls">',
    ]
    for i, w in enumerate(walls):
        lines.append("  " + w.to_mjcf(f"wall_{i:03d}", ppm, origin_px, h_m, t_m, group, mat))
    lines += [
        "    </body>",
        "  </worldbody>",
        "</mujoco>",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(
        description="Convierte imagen/PDF en paredes MuJoCo (v4)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("input", type=Path, help="Imagen PNG/JPG/BMP/TIFF o PDF")
    p.add_argument("--output", "-o", type=Path, default=None)
    p.add_argument("--ppm",   type=float, default=None, help="Píxeles/metro (salta calibración)")
    p.add_argument("--pdf-dpi", type=int, default=300)

    # Detección
    p.add_argument("--blur",           type=int,   default=3)
    p.add_argument("--dark-thresh",    type=int,   default=80,  help="Umbral V/L para píxeles oscuros")
    p.add_argument("--closing",        type=int,   default=5,   help="Cierre morfológico")
    p.add_argument("--invert",         action="store_true",     help="Imagen con fondo negro")
    p.add_argument("--min-line",       type=int,   default=30,  help="Longitud mínima Hough (px)")
    p.add_argument("--max-gap",        type=int,   default=15,  help="Hueco máximo Hough (px)")
    p.add_argument("--hough-thr",      type=int,   default=25)
    p.add_argument("--merge-dist",     type=float, default=10.0)
    p.add_argument("--no-text-filter", action="store_true")
    p.add_argument("--orient", action="store_true", help="Filtrar por orientación dominante (desactivado por defecto)")
    p.add_argument("--orient-tol",     type=float, default=12.0)

    # Geometría
    p.add_argument("--wall-height",    type=float, default=2.5)
    p.add_argument("--wall-thickness", type=float, default=0.15)
    p.add_argument("--group",          type=int,   default=3)
    p.add_argument("--material",       default="wall_mat")

    # Flujo
    p.add_argument("--no-preview-2d",  action="store_true")
    p.add_argument("--no-preview-3d",  action="store_true")
    p.add_argument("--standalone",     action="store_true", help="Genera escena completa (no fragmento)")
    p.add_argument("--save-debug",     action="store_true", help="Exporta imágenes de debug")
    return p.parse_args()


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    args = parse_args()
    if not args.input.exists():
        sys.exit(f"ERROR: no existe '{args.input}'")

    print("=" * 64)
    print("  image_to_mujoco  v4")
    print("=" * 64)

    # 1. Carga ─────────────────────────────────────────────────────────────────
    print(f"  Entrada: {args.input}")
    img = load_input(args.input, args.pdf_dpi)
    H, W = img.shape[:2]
    print(f"  Resolución: {W}×{H} px")

    # Reducir si es enorme (evitar OOM en imágenes 4K+)
    MAX_DIM = 4096
    if max(W, H) > MAX_DIM:
        scale = MAX_DIM / max(W, H)
        img = cv2.resize(img, (int(W*scale), int(H*scale)), interpolation=cv2.INTER_AREA)
        H, W = img.shape[:2]
        print(f"  [auto-resize] → {W}×{H} px")

    # 2. Máscara binaria ───────────────────────────────────────────────────────
    print("  Construyendo máscara de paredes…")
    mask = build_wall_mask(img, args.blur, args.dark_thresh, args.closing, args.invert)

    if not args.no_text_filter:
        before = int(np.count_nonzero(mask))
        mask, kept_cc = remove_text_noise(mask)
        after  = int(np.count_nonzero(mask))
        print(f"  Filtro texto: {100*(before-after)/max(before,1):.1f}% eliminado | CC: {kept_cc}")

    if args.save_debug:
        dbg_path = args.input.with_name(args.input.stem + "_debug_mask.png")
        cv2.imwrite(str(dbg_path), mask)
        print(f"  Debug máscara: {dbg_path}")

    # 3. Calibración ───────────────────────────────────────────────────────────
    if args.ppm is not None:
        ppm = args.ppm
        print(f"  Escala (CLI): {ppm:.3f} px/m")
    else:
        print("  Abriendo calibración…")
        d = CalibrationDialog(img)
        ppm = d.run()
        if ppm is None:
            print("  Calibración cancelada.")
            sys.exit(0)
        print(f"  Escala: {ppm:.3f} px/m")

    # 4. Detección ─────────────────────────────────────────────────────────────
    print("\n  Detectando paredes…")
    w_hough = detect_hough(mask, args.min_line, args.max_gap, args.hough_thr)
    w_cc    = detect_components(mask)
    print(f"  Hough: {len(w_hough)}  |  Componentes: {len(w_cc)}")

    walls = merge_colinear(w_hough + w_cc, args.merge_dist)
    print(f"  Tras fusión: {len(walls)}")

    if args.orient:
        walls = filter_dominant_orientation(walls, args.orient_tol)
        print(f"  (filtro orientación activo)")

    walls = [w for w in walls if w.length >= max(15.0, args.min_line * 0.5)]
    print(f"  Final: {len(walls)}")

    if not walls:
        print("\nNo se detectó ninguna pared. Ajusta parámetros.")
        sys.exit(1)

    # 5. Editor 2D ─────────────────────────────────────────────────────────────
    if not args.no_preview_2d:
        print("  Abriendo editor 2D…")
        _dparams = dict(
            min_line=args.min_line, max_gap=args.max_gap,
            hough_thr=args.hough_thr, merge_dist=args.merge_dist,
        )
        ed = WallEditor(img, walls, mask=mask, detect_params=_dparams)
        if not ed.run():
            print("Cancelado por el usuario.")
            sys.exit(0)
        walls = ed.walls
        print(f"  Paredes tras edición: {len(walls)}")

    # 6. Preview 3D ────────────────────────────────────────────────────────────
    if not args.no_preview_3d and HAS_3D:
        print("  Abriendo preview 3D…")
        ok = show_3d_preview(walls, ppm, W, H, args.wall_height, args.wall_thickness)
        if not ok:
            print("Cancelado en preview 3D.")
            sys.exit(0)
    elif not args.no_preview_3d and not HAS_3D:
        print("  [INFO] pip install pygame PyOpenGL para habilitar preview 3D")

    # 7. Exportar XML ──────────────────────────────────────────────────────────
    if args.output:
        out = args.output
    else:
        suffix = "_scene.xml" if args.standalone else "_walls.xml"
        default = args.input.with_name(args.input.stem + suffix)
        root = tk.Tk(); root.withdraw()
        out_str = filedialog.asksaveasfilename(
            title="Guardar XML MuJoCo",
            initialfile=default.name, initialdir=str(default.parent),
            defaultextension=".xml",
            filetypes=[("XML MuJoCo", "*.xml"), ("Todos", "*.*")],
        )
        root.destroy()
        out = Path(out_str) if out_str else default

    out.parent.mkdir(parents=True, exist_ok=True)
    origin_px = (W / 2.0, H / 2.0)

    if args.standalone:
        write_standalone(walls, out, ppm, origin_px,
                         args.wall_height, args.wall_thickness,
                         args.group, str(args.input), args.material)
        print(f"\n  ✔  Escena completa: {out}")
    else:
        write_fragment(walls, out, ppm, origin_px,
                       args.wall_height, args.wall_thickness,
                       args.group, str(args.input), args.material)
        print(f"\n  ✔  Fragmento guardado: {out}")
        print(f'     Incluir en scene.xml con: <include file="{out.name}"/>')

    print("=" * 64)


if __name__ == "__main__":
    main()
