#!/usr/bin/env python3
"""
Material Property Cross-Validation
====================================

Cross-validates Aethermor's material database against multiple independent
published sources.  Each material property is checked against reference
values from 2-3 independent sources.

SOURCES:
  - CRC Handbook of Chemistry and Physics, 104th Edition (2023)
  - ASM International Materials Database (online)
  - NIST Standard Reference Data (webbook.nist.gov)
  - Ioffe Physico-Technical Institute semiconductor database
  - Shackelford & Alexander, "CRC Materials Science & Engineering Handbook"
  - Manufacturer datasheets (Element Six for diamond, II-VI for SiC)

METHODOLOGY:
  For each of the 21 built-in materials, we check:
  1. Thermal conductivity k [W/(m·K)] against 2+ published reference values
  2. Density ρ [kg/m³] against published reference
  3. Specific heat c_p [J/(kg·K)] against published reference
  4. Derived properties: thermal diffusivity α = k/(ρ·c_p)
  5. Physical consistency: all values positive, physically ordered
"""
import sys
import os
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from aethermor.physics.materials import get_material, list_materials

_pass = 0
_fail = 0


def sep(title):
    print(f"\n{'=' * 72}")
    print(f"  {title}")
    print(f"{'=' * 72}\n")


def check(desc, value, lo, hi, unit=""):
    global _pass, _fail
    ok = lo <= value <= hi
    tag = "PASS" if ok else "FAIL"
    if ok:
        _pass += 1
    else:
        _fail += 1
    u = f" {unit}" if unit else ""
    print(f"  [{tag}]  {desc}")
    print(f"         Got: {value:.4g}{u}")
    print(f"         Expected: [{lo:.4g}, {hi:.4g}]{u}")
    return ok


# ======================================================================
#  Reference data: published values from multiple independent sources
# ======================================================================
#
# Format: (lo, hi) = acceptable range spanning published reference values
# with ±5–15% to account for measurement conditions (temperature,
# crystal orientation, purity, etc.)

REFERENCE_DATA = {
    "silicon": {
        # CRC: 148, ASM: 130-150 (depends on doping), Ioffe: 150
        "k": (125, 160),
        # CRC: 2329, ASM: 2330, NIST: 2329
        "rho": (2300, 2360),
        # CRC: 700-710, ASM: 702, NIST: 705
        "cp": (680, 730),
        # CRC: 1.12 eV, Ioffe: 1.12
        "bandgap": (1.10, 1.14),
        "refs": "CRC 104th, ASM, Ioffe Institute",
    },
    "silicon_dioxide": {
        # CRC: 1.3-1.5, ASM: 1.4, Shackelford: 1.38
        "k": (1.2, 1.6),
        # CRC: 2200-2650 (depends on form), ASM: 2200 (amorphous)
        "rho": (2100, 2300),
        # CRC: 730-740, ASM: 745
        "cp": (700, 770),
        "bandgap": (8.5, 9.5),
        "refs": "CRC, ASM, Shackelford",
    },
    "gallium_arsenide": {
        # CRC: 55, Ioffe: 46-55, ASM: 55
        "k": (42, 60),
        # CRC: 5316-5320, Ioffe: 5316
        "rho": (5280, 5360),
        # CRC: 327-330, Ioffe: 330
        "cp": (310, 350),
        "bandgap": (1.40, 1.44),
        "refs": "CRC, Ioffe Institute, ASM",
    },
    "diamond": {
        # CRC: 2000-2200 (natural type IIa), Element Six: 1800-2200
        # CVD single crystal: up to 2200, polycrystalline: 1000-1800
        "k": (1800, 2400),
        # CRC: 3510-3520
        "rho": (3490, 3530),
        # CRC: 509-520, ASM: 510
        "cp": (490, 540),
        "bandgap": (5.45, 5.50),
        "refs": "CRC, Element Six, ASM",
    },
    "graphene_layer": {
        # Balandin (2008 Science): 4800-5300 in-plane, suspended
        # Ghosh et al. (2008): 3000-5000 depending on substrate
        "k": (3000, 5500),
        # Density of graphite: 2267; monolayer effective ~2267
        "rho": (2200, 2350),
        # Close to graphite: 700-710
        "cp": (680, 730),
        "bandgap": (0.0, 0.01),  # zero-gap semiconductor / semimetal
        "refs": "Balandin (2008), Ghosh et al., CRC",
    },
    "copper": {
        # CRC: 401, ASM: 398-401, NIST: 401
        "k": (385, 415),
        # CRC: 8960, ASM: 8960, NIST: 8960
        "rho": (8900, 9000),
        # CRC: 385, ASM: 385
        "cp": (375, 395),
        "bandgap": (0.0, 0.0),  # metal
        "refs": "CRC, ASM, NIST",
    },
    "indium_phosphide": {
        # CRC: 68, Ioffe: 68, ASM: 68
        "k": (60, 75),
        # CRC: 4810, Ioffe: 4787-4810
        "rho": (4750, 4850),
        # CRC: 310, Ioffe: 310
        "cp": (295, 330),
        "bandgap": (1.33, 1.37),
        "refs": "CRC, Ioffe Institute, ASM",
    },
    "silicon_carbide": {
        # II-VI/Wolfspeed: 490 (4H-SiC), CRC: 370-490 (polytype-dependent)
        # Ioffe: 370-490
        "k": (350, 520),
        # CRC: 3210-3220, Ioffe: 3210
        "rho": (3180, 3250),
        # CRC: 690, Ioffe: 670-690
        "cp": (660, 720),
        "bandgap": (3.20, 3.30),
        "refs": "CRC, Wolfspeed/II-VI, Ioffe Institute",
    },
    "gallium_nitride": {
        # CRC: 130, Ioffe: 130, ASM: 130
        # Can vary 130-230 depending on crystal quality
        "k": (120, 150),
        # CRC: 6150, Ioffe: 6100-6150
        "rho": (6050, 6200),
        # CRC: 490, Ioffe: 490
        "cp": (470, 510),
        "bandgap": (3.38, 3.42),
        "refs": "CRC, Ioffe Institute, ASM",
    },
    # ── Metals (heatsinks, interconnects, heat spreaders) ────────────
    "aluminum": {
        # CRC: 237, Incropera: 237, ASM: 237
        "k": (225, 250),
        # CRC: 2700, ASM: 2700, Incropera: 2702
        "rho": (2680, 2720),
        # CRC: 897-903, Incropera: 903, ASM: 897
        "cp": (880, 920),
        "bandgap": (0.0, 0.0),
        "refs": "CRC 104th, Incropera Table A.1, ASM",
    },
    "tungsten": {
        # CRC: 174, ASM: 173-174, Incropera: 174
        "k": (165, 185),
        # CRC: 19300, ASM: 19300, NIST: 19300
        "rho": (19200, 19400),
        # CRC: 132, ASM: 132, Incropera: 132
        "cp": (125, 140),
        "bandgap": (0.0, 0.0),
        "refs": "CRC 104th, ASM, Incropera",
    },
    "molybdenum": {
        # CRC: 138, ASM: 138, Incropera: 138
        "k": (130, 145),
        # CRC: 10220, ASM: 10220
        "rho": (10150, 10300),
        # CRC: 251, ASM: 251
        "cp": (240, 260),
        "bandgap": (0.0, 0.0),
        "refs": "CRC 104th, ASM",
    },
    # ── Ceramics (substrates, packages) ──────────────────────────────
    "aluminum_nitride": {
        # CRC: 170-285, Kyocera: 170 (poly), Tokuyama: 170-230
        "k": (150, 200),
        # CRC: 3260, Kyocera: 3260
        "rho": (3200, 3300),
        # Kyocera: 740, CRC: 740
        "cp": (720, 770),
        "bandgap": (6.1, 6.3),
        "refs": "CRC, Kyocera datasheets, Tokuyama",
    },
    "alumina": {
        # CRC: 25-35 (96% purity), Kyocera: 25-30, ASM: 30
        "k": (22, 38),
        # CRC: 3950, Kyocera: 3800-3950
        "rho": (3800, 4000),
        # CRC: 765, ASM: 775
        "cp": (740, 800),
        "bandgap": (8.5, 9.0),
        "refs": "CRC, Kyocera, ASM",
    },
    "beryllium_oxide": {
        # CRC: 285-330, Materion: 300, ASM: 285-300
        "k": (270, 340),
        # CRC: 3010, Materion: 3010
        "rho": (2950, 3050),
        # CRC: 1020, Materion: 1020-1050
        "cp": (990, 1060),
        "bandgap": (10.4, 10.8),
        "refs": "CRC, Materion datasheets, ASM",
    },
    "sapphire": {
        # CRC: 40-46, Kyocera: 42, ASM: 42
        "k": (38, 48),
        # CRC: 3980, Kyocera: 3980
        "rho": (3950, 4020),
        # CRC: 765, same composition as alumina
        "cp": (740, 800),
        "bandgap": (8.5, 9.0),
        "refs": "CRC, Kyocera datasheets",
    },
    # ── Semiconductors (additional) ──────────────────────────────────
    "germanium": {
        # CRC: 60, Ioffe: 60, ASM: 60
        "k": (55, 65),
        # CRC: 5323, Ioffe: 5323
        "rho": (5280, 5360),
        # CRC: 320, Ioffe: 320
        "cp": (305, 340),
        "bandgap": (0.65, 0.69),
        "refs": "CRC 104th, Ioffe Institute, ASM",
    },
    # ── Packaging / interconnect materials ───────────────────────────
    "solder_sac305": {
        # Snugovsky: 55-60, IPC-9701: 58, various: 55-63
        "k": (50, 65),
        # Various: 7380-7400
        "rho": (7300, 7500),
        # Sn-based: 218-227
        "cp": (200, 240),
        "bandgap": (0.0, 0.0),
        "refs": "Snugovsky et al., IPC-9701",
    },
    "fr4": {
        # IPC-4101: 0.25-0.35 (through-thickness), various: 0.29
        "k": (0.22, 0.40),
        # Various: 1800-1900
        "rho": (1750, 1950),
        # Various: 1000-1200
        "cp": (1000, 1250),
        "bandgap": (0.0, 0.0),
        "refs": "IPC-4101, Isola datasheets",
    },
    "thermal_grease": {
        # Dow Corning TC-5022: 4-5, Shin-Etsu: 3-6, generic: 3-8
        "k": (3.0, 8.0),
        # Silicone-filled: 2300-2700
        "rho": (2200, 2800),
        # Silicone: 1200-1800
        "cp": (1200, 1800),
        "bandgap": (0.0, 0.0),
        "refs": "Dow Corning (Dow), Shin-Etsu datasheets",
    },
    "aluminum_silicon_carbide": {
        # CPS Technologies: 170-200 (63% SiC), Sumitomo: 180
        "k": (160, 210),
        # CPS: 2900-3100
        "rho": (2850, 3150),
        # Composite: 700-800
        "cp": (700, 800),
        "bandgap": (0.0, 0.0),
        "refs": "CPS Technologies, Sumitomo datasheets",
    },
}


# ======================================================================
#  Section 1: Per-Material Property Validation
# ======================================================================

def section_per_material():
    """Check each material's properties against published reference data."""
    sep("SECTION 1: Per-Material Property Validation")

    for mat_name, ref in REFERENCE_DATA.items():
        m = get_material(mat_name)
        print(f"  --- {m.name} ({mat_name}) ---")
        print(f"      Refs: {ref['refs']}")

        check(
            f"{mat_name}: thermal conductivity k",
            m.thermal_conductivity, ref["k"][0], ref["k"][1], "W/(m·K)",
        )
        check(
            f"{mat_name}: density ρ",
            m.density, ref["rho"][0], ref["rho"][1], "kg/m³",
        )
        check(
            f"{mat_name}: specific heat c_p",
            m.specific_heat, ref["cp"][0], ref["cp"][1], "J/(kg·K)",
        )
        if ref["bandgap"][1] > 0:
            check(
                f"{mat_name}: bandgap",
                m.bandgap_eV, ref["bandgap"][0], ref["bandgap"][1], "eV",
            )
        else:
            check(
                f"{mat_name}: bandgap = 0 (metal/semimetal)",
                m.bandgap_eV, 0.0, 0.01, "eV",
            )
        print()


# ======================================================================
#  Section 2: Derived Property Consistency
# ======================================================================

def section_derived():
    """Validate derived properties: thermal diffusivity and volumetric heat capacity."""
    sep("SECTION 2: Derived Property Consistency")

    for mat_name in REFERENCE_DATA:
        m = get_material(mat_name)

        # Thermal diffusivity α = k / (ρ * c_p)
        alpha_expected = m.thermal_conductivity / (m.density * m.specific_heat)
        alpha_actual = m.thermal_diffusivity
        delta = abs(alpha_expected - alpha_actual) / alpha_expected
        check(
            f"{mat_name}: thermal diffusivity self-consistency",
            delta, 0.0, 1e-10, "relative error",
        )

        # Volumetric heat capacity = ρ * c_p
        vhc_expected = m.density * m.specific_heat
        vhc_actual = m.volumetric_heat_capacity
        delta_vhc = abs(vhc_expected - vhc_actual) / vhc_expected
        check(
            f"{mat_name}: volumetric heat capacity self-consistency",
            delta_vhc, 0.0, 1e-10, "relative error",
        )


# ======================================================================
#  Section 3: Physical Ordering Constraints
# ======================================================================

def section_ordering():
    """Verify physical ordering that must hold across materials."""
    sep("SECTION 3: Physical Ordering Constraints")

    materials = {name: get_material(name) for name in REFERENCE_DATA}

    # Core semiconductor thermal conductivity ordering (must hold)
    k_order = [
        ("diamond", "silicon_carbide"),
        ("silicon_carbide", "silicon"),
        ("silicon", "gallium_nitride"),
        ("gallium_nitride", "indium_phosphide"),
        ("indium_phosphide", "gallium_arsenide"),
        ("gallium_arsenide", "silicon_dioxide"),
    ]
    for better, worse in k_order:
        k_b = materials[better].thermal_conductivity
        k_w = materials[worse].thermal_conductivity
        check(
            f"k ordering: {better} ({k_b}) > {worse} ({k_w})",
            k_b / k_w, 1.01, 10000, "ratio",
        )

    # Metal thermal conductivity ordering
    check(
        "Copper k > Aluminum k > Tungsten k > Molybdenum k",
        1 if (materials["copper"].thermal_conductivity >
              materials["aluminum"].thermal_conductivity >
              materials["tungsten"].thermal_conductivity >
              materials["molybdenum"].thermal_conductivity) else 0,
        1, 1, "",
    )

    # Ceramic thermal conductivity ordering
    check(
        "BeO k > AlN k > sapphire k > alumina k",
        1 if (materials["beryllium_oxide"].thermal_conductivity >
              materials["aluminum_nitride"].thermal_conductivity >
              materials["sapphire"].thermal_conductivity >
              materials["alumina"].thermal_conductivity) else 0,
        1, 1, "",
    )

    # Copper should have highest k among metals in database
    check(
        "Copper k > all other metals",
        materials["copper"].thermal_conductivity,
        max(materials[n].thermal_conductivity
            for n in ["aluminum", "tungsten", "molybdenum"]),
        10000,
        "W/(m·K)",
    )

    # Graphene should have highest k overall
    check(
        "Graphene k is highest in database",
        materials["graphene_layer"].thermal_conductivity,
        materials["diamond"].thermal_conductivity,
        10000,
        "W/(m·K)",
    )

    # Tungsten is densest material in database
    check(
        "Tungsten density highest in database",
        materials["tungsten"].density,
        max(materials[n].density for n in materials if n != "tungsten"),
        25000,
        "kg/m³",
    )

    # FR-4 k is very low (thermal bottleneck)
    check(
        "FR-4 k < 1 (thermal bottleneck material)",
        materials["fr4"].thermal_conductivity,
        0.1, 1.0,
        "W/(m·K)",
    )

    # All bandgaps non-negative
    for name, m in materials.items():
        check(
            f"{name}: bandgap ≥ 0",
            m.bandgap_eV, 0.0, 12.0, "eV",
        )

    # Wide-bandgap materials (SiC, GaN, Diamond) > narrow-bandgap (Si, GaAs, InP, Ge)
    for wide in ["silicon_carbide", "gallium_nitride", "diamond"]:
        for narrow in ["silicon", "gallium_arsenide", "indium_phosphide"]:
            check(
                f"Bandgap: {wide} > {narrow}",
                materials[wide].bandgap_eV / materials[narrow].bandgap_eV,
                1.5, 10, "ratio",
            )


# ======================================================================
#  Section 4: Thermal Diffusivity Rankings
# ======================================================================

def section_diffusivity():
    """Validate thermal diffusivity rankings against published data."""
    sep("SECTION 4: Thermal Diffusivity Rankings")

    materials = {name: get_material(name) for name in REFERENCE_DATA}

    # Published thermal diffusivity values (m²/s) at 300K:
    # Diamond: ~1200e-6, Cu: ~117e-6, SiC: ~160e-6, Si: ~88e-6
    # GaN: ~43e-6, GaAs: ~31e-6, InP: ~46e-6, SiO2: ~0.87e-6
    published_alpha = {
        "diamond": (800e-6, 1400e-6),  # varies with crystal quality
        "copper": (100e-6, 130e-6),
        "silicon_carbide": (100e-6, 250e-6),
        "silicon": (70e-6, 100e-6),
        "graphene_layer": (2000e-6, 4000e-6),  # in-plane, highly variable
        "gallium_nitride": (35e-6, 55e-6),
        "indium_phosphide": (35e-6, 55e-6),
        "gallium_arsenide": (25e-6, 40e-6),
        "silicon_dioxide": (0.5e-6, 1.5e-6),
        # New materials
        "aluminum": (85e-6, 105e-6),       # CRC: ~97e-6
        "tungsten": (60e-6, 75e-6),         # CRC: ~68e-6
        "molybdenum": (45e-6, 60e-6),       # CRC: ~54e-6
        "aluminum_nitride": (60e-6, 80e-6), # varies with crystal quality
        "alumina": (7e-6, 12e-6),           # CRC: ~9.9e-6
        "beryllium_oxide": (85e-6, 110e-6), # CRC: ~98e-6
        "sapphire": (10e-6, 16e-6),         # CRC: ~13.8e-6
        "germanium": (30e-6, 40e-6),        # CRC: ~35e-6
        "solder_sac305": (30e-6, 40e-6),    # Sn alloy
        "fr4": (0.1e-6, 0.2e-6),            # very low (thermal bottleneck)
        "thermal_grease": (1.0e-6, 2.0e-6), # filled silicone
        "aluminum_silicon_carbide": (70e-6, 90e-6),  # MMC
    }

    for name, (lo, hi) in published_alpha.items():
        m = materials[name]
        check(
            f"{name}: thermal diffusivity in published range",
            m.thermal_diffusivity, lo, hi, "m²/s",
        )


# ======================================================================
#  Section 5: Registry Completeness
# ======================================================================

def section_registry():
    """Verify material registry is complete and functional."""
    sep("SECTION 5: Registry Completeness")

    all_names = list_materials()
    check(
        "Registry has 21 built-in materials",
        len(all_names), 21, 21, "materials",
    )

    expected = {
        "silicon", "silicon_dioxide", "gallium_arsenide", "diamond",
        "graphene_layer", "copper", "indium_phosphide", "silicon_carbide",
        "gallium_nitride",
        # New materials
        "aluminum", "tungsten", "molybdenum",
        "aluminum_nitride", "alumina", "beryllium_oxide", "sapphire",
        "germanium",
        "solder_sac305", "fr4", "thermal_grease", "aluminum_silicon_carbide",
    }
    present = set(all_names)
    missing = expected - present
    check(
        f"All expected materials present (missing: {missing or 'none'})",
        len(missing), 0, 0, "",
    )

    # Case-insensitive lookup
    try:
        m1 = get_material("Silicon")
        m2 = get_material("SILICON")
        m3 = get_material("silicon")
        same = (m1.name == m2.name == m3.name)
    except Exception:
        same = False
    check(
        "Case-insensitive material lookup works",
        1 if same else 0, 1, 1, "",
    )


# ======================================================================
#  Main
# ======================================================================

def main():
    global _pass, _fail

    print("Aethermor Material Property Cross-Validation")
    print("=" * 72)
    print()
    print("Cross-validating 21 materials against CRC Handbook, ASM, NIST,")
    print("Ioffe Institute, and manufacturer datasheets.")
    print()

    t_start = time.time()

    section_per_material()
    section_derived()
    section_ordering()
    section_diffusivity()
    section_registry()

    elapsed = time.time() - t_start
    n_total = _pass + _fail

    sep(f"RESULTS: {_pass} passed, {_fail} failed  ({n_total} checks in {elapsed:.1f}s)")

    if _fail == 0:
        print()
        print("  All checks passed.")
        print()
        print("  Every material property in Aethermor's database falls within")
        print("  published reference ranges from 2-3 independent sources.")
        print("  Derived properties are self-consistent, physical ordering")
        print("  constraints are satisfied, and the material registry is")
        print("  complete and functional.")
    else:
        print(f"\n  {_fail} check(s) failed. Review output above.")

    print()
    print("References:")
    print("  [1] CRC Handbook of Chemistry and Physics, 104th Ed. (2023)")
    print("  [2] ASM International Materials Database")
    print("  [3] NIST Standard Reference Data (webbook.nist.gov)")
    print("  [4] Ioffe Physico-Technical Institute Semiconductor DB")
    print("  [5] Shackelford & Alexander, CRC Materials Science Handbook")
    print("  [6] Balandin et al., Nano Letters 8(3), 902-907 (2008)")
    print("  [7] Element Six / Wolfspeed manufacturer datasheets")
    print("  [8] Incropera et al., Fundamentals of Heat and Mass Transfer")
    print("  [9] Kyocera / Tokuyama ceramic substrate datasheets")
    print("  [10] Materion beryllium oxide datasheets")
    print("  [11] Snugovsky et al., SAC solder alloy data; IPC-9701")
    print("  [12] IPC-4101 (FR-4 laminate specification)")
    print("  [13] CPS Technologies / Sumitomo (AlSiC composites)")

    return _fail == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
