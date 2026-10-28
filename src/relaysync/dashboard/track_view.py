"""Visualisasi lintasan estafet horizontal berbasis SVG untuk halaman Live."""
from __future__ import annotations

from relaysync.domain.models import SessionSnapshot
from relaysync.domain.states import STATE_LABELS, State

STATE_COLORS: dict[State, tuple[str, str]] = {
    State.IDLE: ("#475569", "#f1f5f9"),
    State.APPROACHING: ("#1d4ed8", "#dbeafe"),
    State.OPTIMAL_TRANSFER_ZONE: ("#15803d", "#dcfce7"),
    State.GAP_TOO_FAR_ALERT: ("#b91c1c", "#fee2e2"),
    State.HANDOFF_DONE: ("#0f766e", "#ccfbf1"),
    State.NO_DATA: ("#92400e", "#fef3c7"),
}


def state_badge_html(state: State, reason: str) -> str:
    fg, bg = STATE_COLORS.get(state, ("#334155", "#f8fafc"))
    label = STATE_LABELS.get(state, state.value)
    return (
        f'<div style="background:{bg};border-left:6px solid {fg};padding:14px 18px;'
        f'border-radius:8px;margin-bottom:14px;">'
        f'<div style="font-size:1.35rem;font-weight:700;color:{fg};">'
        f"STATUS: {label} ({state.value})</div>"
        f'<div style="font-size:0.95rem;color:#1e293b;margin-top:4px;">{reason}</div>'
        f"</div>"
    )


def track_svg_html(snap: SessionSnapshot, entry_margin_m: float = 5.0) -> str:
    """Gambar lintasan horizontal dengan zona transisi, posisi x1, x2, dan anotasi gap."""
    total_m = max(snap.leg_length_m + snap.zone_length_m + 15.0, snap.x1_m + 10.0, snap.x2_m + 10.0)
    width, height = 860, 175
    pad_l, pad_r = 45, 35
    usable = width - pad_l - pad_r

    def to_px(pos_m: float) -> float:
        clamped = max(0.0, min(total_m, pos_m))
        return pad_l + (clamped / total_m) * usable

    z_start = snap.leg_length_m
    z_end = snap.leg_length_m + snap.zone_length_m
    entry_start = max(0.0, z_start - entry_margin_m)

    px_entry = to_px(entry_start)
    px_z_start = to_px(z_start)
    px_z_end = to_px(z_end)
    px_x1 = to_px(snap.x1_m)
    px_x2 = to_px(snap.x2_m)
    px_mid = (px_x1 + px_x2) / 2.0

    ticks_svg = []
    step_m = 10 if total_m <= 120 else 20
    m = 0
    while m <= int(total_m):
        tx = to_px(float(m))
        ticks_svg.append(
            f'<line x1="{tx:.1f}" y1="115" x2="{tx:.1f}" y2="123" stroke="#64748b" stroke-width="1.5"/>'
            f'<text x="{tx:.1f}" y="138" text-anchor="middle" font-size="11" fill="#475569">{m} m</text>'
        )
        m += step_m

    return f"""
    <div style="background:#ffffff;border:1px solid #cbd5e1;border-radius:8px;padding:10px 12px;margin-bottom:14px;">
      <div style="font-size:0.9rem;font-weight:600;color:#334155;margin-bottom:4px;">
        Visualisasi Lintasan Estafet (Zona Transisi: {z_start:g} m sampai {z_end:g} m)
      </div>
      <svg viewBox="0 0 {width} {height}" width="100%" height="175" xmlns="http://www.w3.org/2000/svg">
        <!-- Latar lintasan -->
        <rect x="{pad_l}" y="65" width="{usable}" height="50" rx="6" fill="#f1f5f9" stroke="#94a3b8" stroke-width="1.5"/>
        <!-- Pra-zona (entry margin) -->
        <rect x="{px_entry:.1f}" y="65" width="{max(0.0, px_z_start - px_entry):.1f}" height="50" fill="#fef9c3" opacity="0.85"/>
        <!-- Pita Zona Transisi -->
        <rect x="{px_z_start:.1f}" y="65" width="{max(2.0, px_z_end - px_z_start):.1f}" height="50" fill="#bbf7d0" stroke="#16a34a" stroke-width="1.5"/>
        <text x="{(px_z_start + px_z_end)/2:.1f}" y="57" text-anchor="middle" font-size="11" font-weight="600" fill="#15803d">
          ZONA TRANSISI ({z_start:g}-{z_end:g} m)
        </text>
        <!-- Garis hubung gap -->
        <line x1="{px_x1:.1f}" y1="90" x2="{px_x2:.1f}" y2="90" stroke="#475569" stroke-width="2" stroke-dasharray="5,4"/>
        <rect x="{px_mid - 42:.1f}" y="22" width="84" height="22" rx="4" fill="#0f172a"/>
        <text x="{px_mid:.1f}" y="37" text-anchor="middle" font-size="11" font-weight="600" fill="#ffffff">
          Gap: {snap.gap_m:.1f} m
        </text>
        <!-- Penanda Pelari 1 (edge1) -->
        <circle cx="{px_x1:.1f}" cy="90" r="11" fill="#2563eb" stroke="#ffffff" stroke-width="2"/>
        <text x="{px_x1:.1f}" y="94" text-anchor="middle" font-size="10" font-weight="700" fill="#ffffff">P1</text>
        <text x="{px_x1:.1f}" y="156" text-anchor="middle" font-size="11" font-weight="600" fill="#1d4ed8">
          P1: {snap.x1_m:.1f} m ({snap.v1_mps:.1f} m/s)
        </text>
        <!-- Penanda Pelari 2 (edge2) -->
        <circle cx="{px_x2:.1f}" cy="90" r="11" fill="#ea580c" stroke="#ffffff" stroke-width="2"/>
        <text x="{px_x2:.1f}" y="94" text-anchor="middle" font-size="10" font-weight="700" fill="#ffffff">P2</text>
        <text x="{px_x2:.1f}" y="170" text-anchor="middle" font-size="11" font-weight="600" fill="#c2410c">
          P2: {snap.x2_m:.1f} m ({snap.v2_mps:.1f} m/s)
        </text>
        {"".join(ticks_svg)}
      </svg>
    </div>
    """
