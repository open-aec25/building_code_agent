# ASCE 7-16 MWFRS Wind Pressure Calculation — Systematic Workflow
## Chapter 27 Directional Procedure | Enclosed Rigid Building

This document describes the step-by-step decision logic and calculation workflow used to produce MWFRS wind pressures per ASCE 7-16. It is written to be method-agnostic so it can serve as a reference checklist against any custom calculation workflow.

---

## Phase 1 — Collect and Classify Inputs

### 1.1 Building Geometry
- Identify plan dimensions: length (L) and width (B)
- Identify mean roof height (h)
- Identify eave height
- For flat roofs: mean roof height = eave height
- Identify roof type (flat, gable, hip, monoslope, mansard)
- Identify roof slope θ (flat = 0°)

### 1.2 Site and Code Parameters
- Confirm the governing standard: ASCE 7-16 (not 7-10 or 7-22)
- Confirm the design method: Chapter 27 Directional Procedure (not Chapter 28 Envelope Procedure)
- Determine Risk Category from Table 1.5-1
- Obtain Basic Wind Speed V (mph) from Figure 26.5-1A for the applicable Risk Category
- Determine Exposure Category (B, C, or D) per §26.7 based on surface roughness upwind of the site
- Determine Enclosure Classification (enclosed, partially enclosed, open) per §26.12

### 1.3 Assign Code Factors
- Wind Directionality Factor K_d — Table 26.6-1 (buildings = 0.85)
- Topographic Factor K_zt — §26.8; if topography not significant, K_zt = 1.0
- Ground Elevation Factor K_e — §26.9; K_e = exp(−0.0000362 × z_gl); at sea level = 1.0
- Gust Effect Factor G — §26.11; for rigid buildings (natural frequency ≥ 1 Hz), G = 0.85
- Internal Pressure Coefficient GC_pi — Table 26.13-1
  - Enclosed buildings: GC_pi = +0.18 and −0.18 (both cases must be evaluated)
  - Partially enclosed: GC_pi = +0.55 and −0.55
  - Open buildings: GC_pi = 0.0

---

## Phase 2 — Compute Velocity Pressure

### 2.1 Determine Velocity Pressure Exposure Coefficient K_z
- Use Table 26.10-1 for the applicable Exposure Category
- K_z varies with height z above ground
- For MWFRS walls: evaluate K_z at each height increment if building is tall; for low-rise buildings where z ≤ 15 ft, K_z is taken at the tabulated minimum
- For MWFRS roof and leeward/side walls: evaluate at z = h (mean roof height) to get K_h
- Exposure C minimum (z ≤ 15 ft): K_z = 0.85
- Exposure B minimum (z ≤ 30 ft): K_z = 0.57
- Exposure D minimum (z ≤ 15 ft): K_z = 1.03

### 2.2 Compute Velocity Pressure q_z
Apply ASCE 7-16 Eq. 26.10-1:

```
q_z = 0.00256 × K_z × K_zt × K_d × K_e × V²   (psf, V in mph)
```

- For windward wall: q_z varies with height z (use K_z at each height)
- For all other surfaces (leeward wall, side walls, roof): use q_h = q_z evaluated at z = h
- For internal pressure (enclosed building): q_i = q_h

### 2.3 Record q_h
This single value drives all subsequent pressure calculations except the windward wall (which uses q_z per height increment, though for buildings where h ≤ 15 ft, q_z = q_h throughout).

---

## Phase 3 — Determine Geometric Ratios

### 3.1 Compute L/B Ratio
```
L/B = building dimension along wind / building dimension perpendicular to wind
```
- Needed to select leeward wall C_p from Figure 27.3-1
- Both wind directions must be checked; L and B swap when wind direction rotates 90°

### 3.2 Compute h/L Ratio
```
h/L = mean roof height / building dimension along wind direction
```
- Needed to define roof pressure zones from Figure 27.3-1
- h/L determines which row of the flat roof C_p table applies

---

## Phase 4 — Select External Pressure Coefficients C_p

### 4.1 Wall C_p Values (Figure 27.3-1)

**Windward Wall:**
- C_p = +0.8 always, regardless of L/B or h/L

**Leeward Wall:**
- Interpolate from Figure 27.3-1 based on L/B:
  - L/B = 1 → C_p = −0.5
  - L/B = 2 → C_p = −0.3
  - L/B ≥ 4 → C_p = −0.2
  - Interpolate linearly for intermediate values

**Side Walls:**
- C_p = −0.7 always, regardless of geometry

### 4.2 Flat Roof C_p Values (Figure 27.3-1, θ = 0°)

Roof zones are horizontal strips measured from the **windward edge** of the roof:

| Zone | Distance from Windward Edge | C_p (h/L ≤ 0.5) |
|---|---|---|
| Zone 1 | 0 to h | −0.9 |
| Zone 2 | h to 2h | −0.5 |
| Zone 3 | 2h to end (if building depth > 2h) | −0.3 |

- If h/L > 0.5, different C_p values apply (consult Figure 27.3-1 directly)
- For flat roofs, all C_p values are negative (suction/uplift only)
- A positive roof C_p of +0.3 may apply for some pitched roof configurations — not applicable for flat roofs
- Zone boundaries shift when wind direction rotates 90° (L and h/L recalculated)

---

## Phase 5 — Calculate Net Design Pressures

### 5.1 Apply the Net Pressure Equation
ASCE 7-16 Eq. 27.3-1:

```
p = q × G × C_p − q_i × GC_pi
```

Where:
- q = q_z for windward wall (at each height z); q = q_h for all other surfaces
- q_i = q_h for enclosed buildings (internal pressure reference height)
- G = gust effect factor (0.85 for rigid)
- C_p = external pressure coefficient for the surface
- GC_pi = internal pressure coefficient (±0.18 for enclosed)

### 5.2 Evaluate Both GC_pi Cases for Every Surface

For each surface, calculate p twice:

**Case 1 — GC_pi = +0.18 (internal pressure acts outward from building):**
```
p = q × G × C_p − q_i × (+0.18)
```

**Case 2 — GC_pi = −0.18 (internal pressure acts inward into building):**
```
p = q × G × C_p − q_i × (−0.18)
```

### 5.3 Governing Case Logic

| Surface Type | External C_p | Which GC_pi Governs | Why |
|---|---|---|---|
| Windward wall | Positive (+) | GC_pi = −0.18 | Internal suction adds to external compression → larger net inward pressure |
| Leeward wall | Negative (−) | GC_pi = +0.18 | Internal pressure adds to external suction → larger net outward pressure |
| Side walls | Negative (−) | GC_pi = +0.18 | Same as leeward |
| Flat roof (all zones) | Negative (−) | GC_pi = +0.18 | Internal pressure adds to external uplift → larger net uplift |

### 5.4 Sign Convention
- Positive pressure: acts toward (inward on) the surface — compression
- Negative pressure: acts away from (outward on) the surface — suction or uplift

---

## Phase 6 — Wind Direction Checks

### 6.1 Check Both Orthogonal Wind Directions
- Wind 0°: wind acts on the face with dimension B; L is the along-wind depth
- Wind 90°: wind acts on the face with dimension L; B becomes the along-wind depth
- For square buildings (L = B), results are identical for both directions
- For rectangular buildings, L/B and h/L change between directions, changing C_p values and zone extents

### 6.2 Roof Zone Geometry Shifts with Wind Direction
- Roof zone strips always measure from the windward edge of the roof in the current wind direction
- Zone widths (0–h, h–2h, etc.) are measured along the along-wind depth, not the building plan length

---

## Phase 7 — Minimum Wind Pressure Checks

### 7.1 ASCE 7-16 §27.1.5 Minimums
Two separate minimums must be checked:

**Wall minimum:**
```
p_min,wall = 16 psf (net horizontal pressure on projected wall area)
```
- Compare against windward wall net pressure (governing GC_pi case)
- If calculated pressure < 16 psf, use 16 psf

**Roof minimum:**
```
p_min,roof = 8 psf (net uplift pressure on projected roof area)
```
- Compare absolute value of roof zone net pressures
- If |calculated pressure| < 8 psf, use 8 psf

### 7.2 Overall Horizontal Load Minimum
For checking overall horizontal wind load on the MWFRS:
```
F_w,total,min = p_min,wall × A_wall + p_min,roof × A_roof,vertical
```
- A_wall = projected vertical wall area normal to wind = B × h
- A_roof,vertical = projected vertical area of roof (zero for flat roofs)
- Compare against (F_windward − F_leeward): use whichever is greater

---

## Phase 8 — Final Pressure Summary and Governing Values

### 8.1 Tabulate All Results
For each surface, record:
- C_p used and its code source
- External pressure component (q × G × C_p)
- Net pressure for GC_pi = +0.18
- Net pressure for GC_pi = −0.18
- Governing net pressure (larger absolute value)
- Whether minimum pressure controls

### 8.2 Identify Overall Maximum Pressure
- Scan all surfaces and both GC_pi cases
- Identify the single largest absolute pressure in the system
- For most low-rise enclosed buildings, this is typically the windward roof zone under GC_pi = +0.18

---

## Checklist Summary

| Step | Action | Code Reference |
|---|---|---|
| 1 | Classify building geometry and roof type | §26.1 |
| 2 | Determine Risk Category | Table 1.5-1 |
| 3 | Obtain V from wind speed map | Fig. 26.5-1A |
| 4 | Determine Exposure Category | §26.7 |
| 5 | Classify enclosure | §26.12 |
| 6 | Assign K_d | Table 26.6-1 |
| 7 | Compute K_zt | §26.8 |
| 8 | Compute K_e | §26.9 |
| 9 | Assign G (rigid vs. flexible) | §26.11 |
| 10 | Assign GC_pi (both signs) | Table 26.13-1 |
| 11 | Determine K_z / K_h from table | Table 26.10-1 |
| 12 | Compute q_h (and q_z if h > 15 ft) | Eq. 26.10-1 |
| 13 | Compute L/B and h/L | Geometry |
| 14 | Select wall C_p values | Fig. 27.3-1 |
| 15 | Define roof zones and C_p values | Fig. 27.3-1 |
| 16 | Compute net pressures (both GC_pi cases) | Eq. 27.3-1 |
| 17 | Identify governing GC_pi case per surface | §27.3.1 |
| 18 | Check minimum wall pressure (16 psf) | §27.1.5 |
| 19 | Check minimum roof pressure (8 psf) | §27.1.5 |
| 20 | Check both wind directions (0° and 90°) | §27.3.1 |
| 21 | Tabulate final governing pressures | — |

---

## Key Decision Points an Agent Should Verify

1. **Is Chapter 27 (Directional) or Chapter 28 (Envelope) being used?** — They produce different C_p values and are not interchangeable.
2. **Is K_z evaluated at the correct height for each surface?** — Windward uses z; leeward/side/roof use h.
3. **Is q_i set to q_h (not q_z at some other height)?** — For enclosed buildings, §27.1.1 requires q_i = q_h.
4. **Are both GC_pi cases (+0.18 and −0.18) evaluated for every surface?** — Omitting one case is a common shortcut error.
5. **Is the leeward C_p interpolated correctly for L/B?** — A frequent lookup error.
6. **Are roof zones measured from the correct (windward) edge, not the leeward edge?**
7. **Does the roof zone width reset when wind direction changes?** — Zone 1 width = h, but h/L changes.
8. **Is the 16 psf wall minimum checked as a net pressure, not just an external pressure?**
9. **Are both wind directions (0° and 90°) evaluated?** — Required unless building is square and symmetric.
10. **For buildings taller than 60 ft:** Is the windward wall broken into height increments with K_z evaluated at each level? (Not applicable here but a critical workflow branch for taller buildings.)
