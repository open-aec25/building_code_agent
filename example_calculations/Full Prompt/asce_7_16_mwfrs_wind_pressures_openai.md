# ASCE 7-16 MWFRS Wind Pressure Calculation  
**Directional Procedure — Chapter 27**  

## 1. Given Inputs

| Item | Value |
|---|---:|
| Standard | ASCE 7-16 |
| Method | Chapter 27 Directional Procedure |
| System | MWFRS only |
| Building type | Enclosed, rigid, simple rectangular building |
| Roof | Flat |
| Plan dimensions | 30 ft × 30 ft |
| Mean roof height, `h` | 15 ft |
| Eave height | 15 ft |
| Risk Category | II |
| Basic wind speed, `V` | 120 mph |
| Exposure Category | C |
| Topographic factor, `Kzt` | 1.0 |
| Ground elevation factor, `Ke` | 1.0 |
| Wind directionality factor, `Kd` | 0.85 |
| Gust effect factor, `G` | 0.85 |
| Internal pressure coefficient, `GCpi` | ±0.18 |

## 2. Assumptions and Sign Convention

- Building is enclosed, so `qi = qh`.
- Building is rigid, so `G = 0.85`.
- Wind is checked normal to each principal building face. Since the building is square, `L/B = 1.0` for either direction.
- Positive pressure is taken as pressure acting **toward** the surface.
- Negative pressure is suction/uplift acting **away from** the surface.
- This calculation is for **MWFRS only**. Components and cladding pressures are not calculated.

## 3. Velocity Pressure at Mean Roof Height

ASCE 7-16 velocity pressure equation:

```text
qz = 0.00256 Kz Kzt Kd Ke V^2
```

For Exposure C at `z = h = 15 ft`:

```text
Kz = 2.01(z/zg)^(2/alpha)
alpha = 9.5
zg = 900 ft
Kz = 2.01(15/900)^(2/9.5)
Kz = 0.849
```

Therefore:

```text
qh = 0.00256(0.849)(1.0)(0.85)(1.0)(120)^2
qh = 26.60 psf
```

Additional intermediate values:

```text
qG = qh G = (26.60)(0.85) = 22.61 psf
qi GCpi = (26.60)(±0.18) = ±4.79 psf
```

## 4. Wall External Pressure Coefficients

For a rectangular building with `L/B = 1.0`:

| Wall surface | External pressure coefficient, `Cp` |
|---|---:|
| Windward wall | +0.80 |
| Leeward wall | -0.50 |
| Side walls | -0.70 |

Because the building is 30 ft × 30 ft, these wall coefficients are the same for wind applied in either principal direction.

## 5. Flat Roof External Pressure Coefficients and Roof Zones

For the flat roof MWFRS pressure zones:

| Roof zone | Distance from windward roof edge | External pressure coefficient, `Cp` |
|---|---:|---:|
| Roof Zone 1 | 0 to `h` = 0 to 15 ft | -0.90 and -0.18 |
| Roof Zone 2 | `h` to `2h` = 15 to 30 ft | -0.50 and -0.18 |

Because the building length in the wind direction is 30 ft and `2h = 30 ft`, the roof is divided into two strips:
- Zone 1: 0 to 15 ft from the windward roof edge
- Zone 2: 15 to 30 ft from the windward roof edge

No additional downwind roof zone exists because the building length equals `2h`.

## 6. Design Pressure Equation

Given equation:

```text
p = q G Cp - qi GCpi
```

Since the building is enclosed:

```text
qi = qh = 26.60 psf
```

So:

```text
p = (26.60)(0.85)(Cp) - (26.60)(GCpi)
p = 22.61(Cp) - 26.60(GCpi)
```

## 7. Net Design Pressures — Walls

| Wall surface | `Cp` | `p` with `GCpi = +0.18` psf | `p` with `GCpi = -0.18` psf | Governing pressure |
|---|---:|---:|---:|---:|
| Windward wall | +0.80 | +13.30 | +22.88 | +22.88 psf |
| Leeward wall | -0.50 | -16.09 | -6.52 | -16.09 psf |
| Side walls | -0.70 | -20.61 | -11.04 | -20.61 psf |

### Wall Governing Summary

| Wall surface | Governing net design pressure |
|---|---:|
| Windward wall inward pressure | **+22.88 psf** |
| Leeward wall suction | **-16.09 psf** |
| Side wall suction | **-20.61 psf** |

## 8. Net Design Pressures — Flat Roof Zones

| Roof zone | `Cp` case | `Cp` | `p` with `GCpi = +0.18` psf | `p` with `GCpi = -0.18` psf | Governing pressure |
|---|---|---:|---:|---:|---:|
| Zone 1, 0 to 15 ft | Maximum uplift | -0.90 | -25.14 | -15.56 | -25.14 psf |
| Zone 1, 0 to 15 ft | Reduced suction / possible downward case | -0.18 | -8.86 | +0.72 | -8.86 psf uplift / +0.72 psf downward |
| Zone 2, 15 to 30 ft | Maximum uplift | -0.50 | -16.09 | -6.52 | -16.09 psf |
| Zone 2, 15 to 30 ft | Reduced suction / possible downward case | -0.18 | -8.86 | +0.72 | -8.86 psf uplift / +0.72 psf downward |

### Roof Governing Summary

| Roof zone | Governing uplift pressure |
|---|---:|
| Zone 1, 0 to 15 ft from windward roof edge | **-25.14 psf** |
| Zone 2, 15 to 30 ft from windward roof edge | **-16.09 psf** |

The most severe roof uplift occurs in **Roof Zone 1**:

```text
p = -25.14 psf
```

## 9. MWFRS Minimum Wind Pressure Check

ASCE 7-16 MWFRS minimum design wind loading is checked as an overall projected-area load, not as a separate components-and-cladding surface pressure.

For wind normal to either 30 ft face:

```text
Projected wall area = 30 ft × 15 ft = 450 sf
Minimum MWFRS wall force = 16 psf × 450 sf = 7,200 lb
```

Calculated along-wind wall force using external wall pressures:

```text
Windward external pressure = qh G Cp = (26.60)(0.85)(0.80) = 18.09 psf
Leeward external suction = qh G |Cp| = (26.60)(0.85)(0.50) = 11.30 psf

Total along-wind pressure effect = 18.09 + 11.30 = 29.39 psf
Calculated MWFRS force = 29.39 psf × 450 sf = 13,226 lb
```

Comparison:

```text
Calculated MWFRS force = 13,226 lb
Minimum MWFRS force   = 7,200 lb
```

Therefore, the calculated MWFRS wind force **exceeds** the ASCE 7-16 minimum. The minimum MWFRS load check **does not govern**.

For this flat roof, the roof has no vertical projected area normal to the horizontal wind direction for the MWFRS horizontal minimum-load check. No components-and-cladding minimum pressure was applied because this calculation is MWFRS only.

## 10. Final Design Pressure Envelope

### Walls

| Surface | Governing net pressure |
|---|---:|
| Windward wall | **+22.88 psf** |
| Leeward wall | **-16.09 psf** |
| Side walls | **-20.61 psf** |

### Roof

| Roof zone | Governing net uplift pressure |
|---|---:|
| Zone 1, 0 to 15 ft from windward roof edge | **-25.14 psf** |
| Zone 2, 15 to 30 ft from windward roof edge | **-16.09 psf** |

## 11. Notes

- Results are MWFRS pressures only.
- ASCE 7-16 Chapter 27 wind load cases, torsional/eccentric load cases, and structural load combinations are not expanded here.
- Components and cladding pressures may be higher and must be checked separately for roof deck, wall panels, fasteners, edge/corner zones, and similar elements.
- This is a calculation aid and should be reviewed against the adopted building code, project-specific conditions, and a licensed structural engineer’s judgment before use for design.
