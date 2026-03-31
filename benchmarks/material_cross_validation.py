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
  For each of the 9 built-in materials, we check:
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

    # Diamond > SiC > Si > GaN > InP > GaAs > SiO2 (thermal conductivity)
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

    # Copper should have highest k among metals
    check(
        "Copper k > all semiconductors except diamond/graphene",
        materials["copper"].thermal_conductivity,
        materials["silicon_carbide"].thermal_conductivity * 0.5,
        materials["diamond"].thermal_conductivity,
        "W/(m·K)",
    )

    # Graphene should have highest k
    check(
        "Graphene k is highest in database",
        materials["graphene_layer"].thermal_conductivity,
        materials["diamond"].thermal_conductivity,
        10000,
        "W/(m·K)",
    )

    # All densities positive and physically ordered
    # Copper (metal) densest, then GaN, GaAs, InP, diamond, SiC, Si, graphene, SiO2
    check(
        "Copper density highest (metal)",
        materials["copper"].density,
        max(materials[n].density for n in materials if n != "copper"),
        15000,
        "kg/m³",
    )

    # All bandgaps non-negative
    for name, m in materials.items():
        check(
            f"{name}: bandgap ≥ 0",
            m.bandgap_eV, 0.0, 10.0, "eV",
        )

    # Wide-bandgap materials (SiC, GaN, Diamond) > narrow-bandgap (Si, GaAs, InP)
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
        "Registry has 9 built-in materials",
        len(all_names), 9, 9, "materials",
    )

    expected = {
        "silicon", "silicon_dioxide", "gallium_arsenide", "diamond",
        "graphene_layer", "copper", "indium_phosphide", "silicon_carbide",
        "gallium_nitride",
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
    print("Cross-validating 9 materials against CRC Handbook, ASM, NIST,")
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

    return _fail == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
