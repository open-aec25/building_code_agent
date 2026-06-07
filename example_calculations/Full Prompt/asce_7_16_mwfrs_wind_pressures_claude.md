# ASCE 7-16 MWFRS Wind Pressure Calculation
## Chapter 27 Directional Procedure — Enclosed Rigid Building

---

## 1. Project Inputs

| Parameter | Value | Reference |
|---|---|---|
| Standard | ASCE 7-16 | — |
| Method | Chapter 27 Directional Procedure, MWFRS | §27.1 |
| Building Type | Enclosed, Rigid, Simple Rectangular | — |
| Roof Type | Flat (θ = 0°) | — |
| Plan Dimensions | 30 ft × 30 ft (L × B) | — |
| Mean Roof Height | h = 15 ft | — |
| Eave Height | 15 ft (= h, flat roof) | — |
| Risk Category | II | Table 1.5-1 |
| Basic Wind Speed | V = 120 mph | Fig. 26.5-1A |
| Exposure Category | C | §26.7 |
| Topographic Factor | K_zt = 1.0 | §26.8 |
| Ground Elevation Factor | K_e = 1.0 | §26.9 |
| Wind Directionality Factor | K_d = 0.85 | Table 26.6-1 |
| Gust Effect Factor | G = 0.85 (rigid) | §26.11.1 |
| Internal Pressure Coefficient | GC_pi = ±0.18 (enclosed) | Table 26.13-1 |

---

## 2. Geometric Parameters

| Parameter | Calculation | Value |
|---|---|---|
| L/B ratio | 30 ft / 30 ft | **1.0** |
| h/L ratio | 15 ft / 30 ft | **0.5** |
| Building depth along wind (L) | 30 ft | — |
| Building width perpendicular to wind (B) | 30 ft | — |

> **Note:** Wind is considered from both principal directions on this square plan. Since L = B = 30 ft, results are identical for both wind directions.

---

## 3. Step 1 — Velocity Pressure Exposure Coefficient K_h

Per **ASCE 7-16 Table 26.10-1**, Exposure Category C, at height z = h = 15 ft:

$$K_h = 0.85$$

> For Exposure C, K_z = 0.85 is the tabulated value for heights from 0 to 15 ft (the table's minimum zone).

---

## 4. Step 2 — Velocity Pressure q_h

**ASCE 7-16 Eq. 26.10-1:**

$$q_z = 0.00256 \; K_z \; K_{zt} \; K_d \; K_e \; V^2 \quad \text{(psf)}$$

Substituting at z = h = 15 ft:

$$q_h = 0.00256 \times 0.85 \times 1.0 \times 0.85 \times 1.0 \times (120)^2$$

$$q_h = 0.00256 \times 0.85 \times 1.0 \times 0.85 \times 1.0 \times 14{,}400$$

$$\boxed{q_h = 26.63 \text{ psf}}$$

> Since the building height h = 15 ft, the velocity pressure at any height z ≤ h defaults to q_h = 26.63 psf. The windward wall uses this single value throughout its height.

---

## 5. Step 3 — Wall External Pressure Coefficients C_p

**Reference: ASCE 7-16 Figure 27.3-1 (Table for Walls)**

| Wall Surface | C_p | Basis |
|---|---|---|
| Windward Wall | **+0.8** | Always +0.8, all L/B |
| Leeward Wall | **−0.5** | L/B = 1.0 → C_p = −0.5 |
| Side Walls | **−0.7** | Always −0.7 |

> For leeward wall, ASCE 7-16 Fig. 27.3-1 gives: L/B ≤ 1 → C_p = −0.5; L/B = 2 → C_p = −0.3; L/B ≥ 4 → C_p = −0.2. At L/B = 1.0 exactly, C_p = **−0.5** governs.

---

## 6. Step 4 — Flat Roof External Pressure Coefficients C_p

**Reference: ASCE 7-16 Figure 27.3-1 (Flat Roof, θ = 0°)**

Roof zones are measured horizontally from the **windward edge** of the roof:

| Zone | Distance from Windward Edge | C_p | Basis |
|---|---|---|---|
| Zone 1 | 0 to h = 0 to **15 ft** | **−0.9** | Fig. 27.3-1, h/L ≤ 0.5 |
| Zone 2 | h to 2h = 15 to **30 ft** | **−0.5** | Fig. 27.3-1, h/L ≤ 0.5 |

> The building depth = 30 ft = 2h. Zone 1 covers 0–15 ft and Zone 2 covers 15–30 ft. There is no Zone 3 (> 2h) because the building is exactly 2h deep. All roof pressures are uplift (negative). No positive roof C_p applies for flat roofs at h/L = 0.5.

---

## 7. Step 5 — Net Design Pressures: Walls

**ASCE 7-16 Eq. 27.3-1:**

$$p = q \cdot G \cdot C_p - q_i \cdot GC_{pi}$$

Where:
- q = q_h = **26.63 psf** for all surfaces (z ≤ h)
- q_i = q_h = **26.63 psf** (enclosed building, §27.1.1)
- G = 0.85
- GC_pi = **+0.18** (Case 1) or **−0.18** (Case 2)

> Internal pressure term: q_i × GC_pi = 26.63 × 0.18 = **4.79 psf**

---

### 7.1 Windward Wall (C_p = +0.8)

External pressure component:

$$q \cdot G \cdot C_p = 26.63 \times 0.85 \times 0.80 = +18.11 \text{ psf}$$

| Load Case | Net Pressure p | Calculation |
|---|---|---|
| GC_pi = +0.18 (outward) | **+13.32 psf** | 18.11 − 4.79 = +13.32 |
| GC_pi = −0.18 (inward) | **+22.91 psf** ✓ | 18.11 + 4.79 = +22.91 |

> **Governing: +22.91 psf** (net inward/compression). The GC_pi = −0.18 case governs because internal suction adds to external compression.

---

### 7.2 Leeward Wall (C_p = −0.5)

External pressure component:

$$q \cdot G \cdot C_p = 26.63 \times 0.85 \times (-0.50) = -11.32 \text{ psf}$$

| Load Case | Net Pressure p | Calculation |
|---|---|---|
| GC_pi = +0.18 (outward) | **−16.11 psf** ✓ | −11.32 − 4.79 = −16.11 |
| GC_pi = −0.18 (inward) | **−6.53 psf** | −11.32 + 4.79 = −6.53 |

> **Governing: −16.11 psf** (net outward/suction). The GC_pi = +0.18 case governs because internal pressure adds to external suction.

---

### 7.3 Side Walls (C_p = −0.7)

External pressure component:

$$q \cdot G \cdot C_p = 26.63 \times 0.85 \times (-0.70) = -15.85 \text{ psf}$$

| Load Case | Net Pressure p | Calculation |
|---|---|---|
| GC_pi = +0.18 (outward) | **−20.64 psf** ✓ | −15.85 − 4.79 = −20.64 |
| GC_pi = −0.18 (inward) | **−11.05 psf** | −15.85 + 4.79 = −11.05 |

> **Governing: −20.64 psf** (net outward/suction). The GC_pi = +0.18 case governs.

---

## 8. Step 6 — Net Design Pressures: Roof

### 8.1 Roof Zone 1 (0–15 ft from windward edge, C_p = −0.9)

External pressure component:

$$q_h \cdot G \cdot C_p = 26.63 \times 0.85 \times (-0.90) = -20.38 \text{ psf}$$

| Load Case | Net Pressure p | Calculation |
|---|---|---|
| GC_pi = +0.18 (outward) | **−25.17 psf** ✓ | −20.38 − 4.79 = −25.17 |
| GC_pi = −0.18 (inward) | **−15.58 psf** | −20.38 + 4.79 = −15.58 |

> **Governing: −25.17 psf** (maximum uplift). The GC_pi = +0.18 case governs because internal pressure adds to external roof uplift.

---

### 8.2 Roof Zone 2 (15–30 ft from windward edge, C_p = −0.5)

External pressure component:

$$q_h \cdot G \cdot C_p = 26.63 \times 0.85 \times (-0.50) = -11.32 \text{ psf}$$

| Load Case | Net Pressure p | Calculation |
|---|---|---|
| GC_pi = +0.18 (outward) | **−16.11 psf** ✓ | −11.32 − 4.79 = −16.11 |
| GC_pi = −0.18 (inward) | **−6.53 psf** | −11.32 + 4.79 = −6.53 |

> **Governing: −16.11 psf** (maximum uplift). The GC_pi = +0.18 case governs.

---

## 9. Minimum Wind Pressure Check

**ASCE 7-16 §27.1.5** requires that the design wind pressures for MWFRS shall not be less than **16 psf** applied as a net horizontal pressure on the projected vertical area of the building, nor less than **8 psf** applied as a net vertical pressure on the projected horizontal area (roof uplift).

### Wall Check (16 psf minimum)

The controlling windward wall net pressure (GC_pi = −0.18 case):

$$p_{ww,\,\text{gov}} = +22.91 \text{ psf} \geq 16 \text{ psf} \quad \checkmark$$

> **Passes.** Calculated windward pressure of **22.91 psf exceeds the 16 psf minimum**. No adjustment required.

### Roof Check (8 psf minimum)

All roof zones produce uplift pressures greater than 8 psf in magnitude:

- Zone 1 governing: −25.17 psf → |25.17| ≥ 8 psf ✓
- Zone 2 governing: −16.11 psf → |16.11| ≥ 8 psf ✓

> **Passes.** All calculated roof uplift pressures exceed the 8 psf minimum. No adjustment required.

---

## 10. Summary of Results

### 10.1 Key Intermediate Values

| Parameter | Value |
|---|---|
| Basic Wind Speed, V | 120 mph |
| Exposure Coefficient, K_h | 0.85 |
| Velocity Pressure, q_h | **26.63 psf** |
| Internal Pressure Term, q_h × GC_pi | ±4.79 psf |
| L/B Ratio | 1.0 |
| h/L Ratio | 0.5 |

---

### 10.2 Wall Net Design Pressures (psf)

| Surface | C_p | External (q·G·C_p) | GC_pi = +0.18 | GC_pi = −0.18 | **Governing** |
|---|---|---|---|---|---|
| Windward Wall | +0.80 | +18.11 | +13.32 | +22.91 | **+22.91 psf** |
| Leeward Wall | −0.50 | −11.32 | −16.11 | −6.53 | **−16.11 psf** |
| Side Walls | −0.70 | −15.85 | −20.64 | −11.05 | **−20.64 psf** |

Sign convention: **positive = inward (compression); negative = outward (suction/uplift)**

---

### 10.3 Roof Net Design Pressures (psf)

| Zone | Extent | C_p | External (qh·G·C_p) | GC_pi = +0.18 | GC_pi = −0.18 | **Governing** |
|---|---|---|---|---|---|---|
| Zone 1 | 0–15 ft (windward) | −0.90 | −20.38 | −25.17 | −15.58 | **−25.17 psf** |
| Zone 2 | 15–30 ft (leeward) | −0.50 | −11.32 | −16.11 | −6.53 | **−16.11 psf** |

All roof pressures are **uplift (negative)**. The GC_pi = +0.18 case governs for all roof zones.

---

### 10.4 Governing Load Cases Summary

| Surface | Governing Pressure | Governing GC_pi Case | Controls |
|---|---|---|---|
| Windward Wall | **+22.91 psf** (compression) | GC_pi = −0.18 | Max inward load |
| Windward Wall | +13.32 psf (compression) | GC_pi = +0.18 | Min inward load |
| Leeward Wall | **−16.11 psf** (suction) | GC_pi = +0.18 | Max outward load |
| Side Walls | **−20.64 psf** (suction) | GC_pi = +0.18 | Max outward load |
| Roof Zone 1 | **−25.17 psf** (uplift) | GC_pi = +0.18 | Max uplift ← **Overall Max** |
| Roof Zone 2 | **−16.11 psf** (uplift) | GC_pi = +0.18 | Max uplift |

> **Maximum pressure in the system: −25.17 psf uplift** at Roof Zone 1 (windward 0–15 ft), governed by the GC_pi = +0.18 load case.

---

## 11. Code References

| Item | ASCE 7-16 Reference |
|---|---|
| Wind speed map | Figure 26.5-1A |
| Exposure categories | §26.7 |
| K_z / K_h values | Table 26.10-1 |
| Velocity pressure equation | Eq. 26.10-1 |
| Wind directionality factor K_d | Table 26.6-1 |
| Gust effect factor G | §26.11.1 |
| Internal pressure GC_pi | Table 26.13-1 |
| Wall C_p coefficients | Figure 27.3-1 |
| Roof C_p coefficients | Figure 27.3-1 |
| Net pressure equation | Eq. 27.3-1 |
| Minimum wind pressures | §27.1.5 |

---

*Calculation performed per ASCE 7-16, Chapter 27 Directional Procedure, MWFRS only. Does not include components and cladding (C&C) pressures. All pressures are unfactored (ASD/LRFD load combination factors not applied).*
