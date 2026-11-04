# STM32_Board — design review (pre-fabrication)

Reviewed: commit `21a5dfb` of `SohamShete/STM32_Board`, files `STM32_Board/STM32_Board.kicad_sch`
(KiCad 9, 1 sheet, rev 1.0 "STM32 Minimum Viable Board"), `STM32_Board.kicad_pcb` (empty),
`STM32_Board.kicad_pro`. No firmware exists in the repository, so section 3 (firmware) of the brief does not apply.

Method: connectivity extracted with `AUDIT/scripts/sch_netlist.py` (pure Python, no KiCad needed; output in
`AUDIT/out/netlist.txt`). `kicad-cli sch erc` could not be run: Ubuntu 24.04 ships KiCad 7.0.11 which cannot
read KiCad 9 files, and adding the KiCad 9 PPA was not permitted in this sandbox. The ERC-equivalent checks
below (dangling labels, undriven power pins, unconnected pins, missing footprints) are from the script and from
reading the file. Reference documents: ST DS5319 (STM32F103x8/xB datasheet) and AN2586 (Getting started with
STM32F10xxx hardware development); page/section citations are given where a reviewer opened them, and are
marked UNVERIFIED otherwise.

## Summary verdict

**Do not order boards from this state.** The schematic is a correct and tidy *MCU power/reset/boot core*
(decoupling, VDDA filter, VBAT, NRST capacitor, BOOT0 switch all match ST's recommendations), but it is not yet
a board: there is no 3.3 V source, no USB, no SWD header, no crystal, no footprints on 12 of 13 parts, and the
PCB file is empty. The README's "schematic complete" is premature. Ranked findings follow.

Counts: CRITICAL 4 · HIGH 4 · MEDIUM 6 · LOW 6.

---

## CRITICAL — board will not work (or feature cannot work) as drawn

### C1. No 3.3 V power source: `+3.3V` net has no driver
- **Where:** nets `+3.3V` (U1.1 VBAT, U1.24/36/48 VDD, C1–C5, C8, FB1.2, SW1.3) and `+3.3VA` (U1.9 VDDA via FB1).
  Power symbols only: `power:+3.3V` at `STM32_Board.kicad_sch:3419`, `:4028`, `:4365`. No regulator, connector,
  USB VBUS or `PWR_FLAG` anywhere (`AUDIT/out/netlist.txt`, component list has U1, C1–C9, FB1, R1, SW1 only).
- **Evidence:** every `+3.3V` member is a `power_in` or passive pin; KiCad ERC with the project severities
  (`kicad_pro` → `erc.rule_severities.power_pin_not_driven = "error"`) will report *Input Power pin not driven by
  any Output Power pins* on VDD/VDDA/VBAT.
- **Fix:** add the supply. For a USB-powered board: USB VBUS (5 V) → 3.3 V LDO (e.g. AP2112K-3.3, MCP1700-3302E,
  or LD1117S33; 150–250 mA class is ample: STM32F103 at 72 MHz all-peripherals-on draws tens of mA, see DS5319
  current-consumption table) → `+3.3V`. Put a 1–4.7 µF ceramic on the LDO input and ≥1 µF (per the LDO datasheet)
  on its output in addition to the existing C5 10 µF. Dissipation at 5 V→3.3 V, 100 mA is 0.17 W, acceptable in
  SOT-23-5/SOT-89 with a copper pour. Add a `PWR_FLAG` or make the regulator output a `power_out` pin so ERC passes.

### C2. No external crystal, so USB (a stated feature) cannot work
- **Where:** U1.5 PD0-OSC_IN and U1.6 PD1-OSC_OUT are unconnected (`AUDIT/out/netlist.txt`, "Unconnected pins").
- **Evidence:** the STM32F103's USB peripheral needs a 48 MHz clock from the PLL; the PLL must be fed from HSE
  because the internal HSI (±1 % trimmed) does not meet the USB full-speed tolerance (±2500 ppm / 0.25 %). The
  USB clock must be derived from HSE (RM0008 §6.2 "Clocks": "the USB clock ... 48 MHz ... from PLL"; the HSI
  accuracy figures are in DS5319 "HSI oscillator characteristics"). See datasheet citations in §Verification.
- **Fix:** add an 8 MHz crystal (e.g. 3.2×2.5 mm SMD, CL = 10 pF or 12 pF, ESR ≤ 80 Ω) between PD0 and PD1 with two
  load capacitors to GND. Compute the load caps as `C1 = C2 = 2·(CL − Cstray)` with Cstray ≈ 3–5 pF for a short
  layout: CL 10 pF → 2·(10−3) = 14 pF → use **12–15 pF**; CL 12 pF → 18 pF; CL 18 pF → 30 pF (27 or 33 pF).
  Record the chosen crystal CL on the schematic. Keep the crystal within ~10 mm of pins 5/6 with a ground
  guard; no other signals under it. Alternatively use a 3.3 V 8 MHz oscillator into OSC_IN (bypass mode).

### C3. No USB connector, D+ pull-up, or ESD protection — "USB connectivity" does not exist in the design
- **Where:** U1.32 PA11 (USB_DM) and U1.33 PA12 (USB_DP) unconnected (`AUDIT/out/netlist.txt`).
- **Evidence:** the STM32F103 USB transceiver has **no internal D+ pull-up**; a 1.5 kΩ resistor from USB_DP to
  3.3 V is mandatory for the host to enumerate (DS5319 USB characteristics / AN4879 §F1 notes — see §Verification).
- **Fix:** add a USB connector (USB-C 16-pin receptacle with 5.1 kΩ CC1/CC2 pull-downs to GND, or Micro-B);
  VBUS → fuse/polyfuse (e.g. 500 mA) → LDO input (C1). D+ (PA12) ← 1.5 kΩ → `+3.3V` (fixed, or switched by a GPIO
  through a transistor if software-controlled re-enumeration is wanted). Add a USBLC6-2SC6 (or equivalent) ESD array
  on D+/D−/VBUS right at the connector. Series resistors on D+/D− are not required for the F103 driver (its
  output impedance is within the USB spec; see §Verification) — leave 0 Ω pads if you want the option. Optional
  VBUS sense: VBUS → 2×10 kΩ (or 47k/100k) divider → a free FT pin.

### C4. No SWD debug header — the chip cannot be programmed or debugged
- **Where:** U1.34 PA13 (SWDIO) and U1.37 PA14 (SWCLK) unconnected; NRST is only on C9.
- **Evidence:** README lists "SWD debug interface"; the schematic has no connector of any kind. With no UART header
  either, the BOOT0 switch (R1/SW1) has nothing to talk to: the STM32F103 system bootloader only supports USART1
  (PA9/PA10), not USB DFU (AN2606, UNVERIFIED here — see §Verification).
- **Fix:** add a debug header: SWDIO (PA13), SWCLK (PA14), NRST (U1.7 net `NRST`), GND, `+3.3V` (VTref), and
  ideally SWO (PB3). Use the Arm 10-pin 1.27 mm Cortex Debug connector or a 4/5-pin 2.54 mm header / Tag-Connect
  TC2030. Optionally bring out USART1 TX/RX (PA9/PA10) on a header so the BOOT0 switch is actually useful.

---

## HIGH — will block PCB layout or fabrication

### H1. 12 of 13 components have no footprint
- **Where:** C1–C9, FB1, R1, SW1 — `Footprint ""` (`AUDIT/out/bom.csv` column 3 shows `<MISSING>` for all but U1).
- **Evidence:** `STM32_Board.kicad_sch` properties; KiCad's *Update PCB from Schematic* refuses symbols without
  footprints, so the PCB file is necessarily empty (0 footprints, 0 nets in `STM32_Board.kicad_pcb`).
- **Fix:** assign in the schematic (Tools → Assign Footprints): 0603 (or 0402) for 100 nF/10 nF/1 µF, 0805 for the
  10 µF (X5R/X7R, ≥6.3 V) and for FB1 (e.g. `Inductor_SMD:L_0805_2012Metric` for a BLM21 bead, 0603 for BLM18),
  0603 for R1, and a real part for SW1 (e.g. `Button_Switch_SMD:SW_SPDT_PCM12` or the slide switch you will buy).
  Then re-run `AUDIT/scripts/bom.py` — no row should read `<MISSING>`.

### H2. PCB layout does not exist
- **Where:** `STM32_Board/STM32_Board.kicad_pcb` is 2 kB: layer stack and plot settings only, `(net 0 "")`, no
  footprints, tracks, zones or board outline.
- **Evidence:** `grep -c "(footprint " STM32_Board.kicad_pcb` → 0; DRC cannot be run meaningfully.
- **Fix:** after H1, update PCB from schematic. Layout guidance for this design: 2-layer, solid GND on B.Cu;
  each 100 nF within 2 mm of its VDD pin (C1→pin 24, C2→pin 36, C3→pin 48, C4→pin 1 VBAT) with the GND side
  via'd straight down; C6/C7 at pin 9 (VDDA) with FB1 upstream; crystal + load caps adjacent to pins 5/6 with a
  local ground island tied to the plane at one point; USB D+/D− as a 90 Ω differential pair, short, no stubs;
  decoupling on the same side as U1. Project rules in `kicad_pro` (0.2 mm track/clearance, 0.6/0.3 mm via) are
  fine for common fabs and for the 0.5 mm-pitch LQFP (0.3 mm pads, 0.2 mm gaps).

### H3. No input protection at all on the (future) power input
- **Where:** nothing between the (missing) supply and `+3.3V`.
- **Fix:** with C1's LDO add: polyfuse or 0.5 A fuse on VBUS, a 5 V TVS (part of USBLC6-2SC6 or a separate
  SMAJ5.0A/PESD5V0), and reverse-polarity protection only if a bare 2-pin DC input is added (Schottky or P-FET).
  An LDO also gives soft start, so no sequencing issue exists between VDD and VDDA (both come from the same rail
  through FB1 — correct per AN2586).

### H4. 37 of the MCU's 48 pins are left floating with no `no_connect` flags
- **Where:** PD0/PD1, PC13–PC15, PA0–PA15, PB0–PB15 (`AUDIT/out/netlist.txt` → 37 "Unconnected pins"; the file
  contains 0 `(no_connect` entries).
- **Evidence:** project ERC severity `pin_not_connected = "error"` → 37 ERC errors. Electrically, floating
  CMOS inputs are acceptable on STM32 *only* because reset state is analog/floating-input and ST recommends
  configuring unused pins as analog in firmware (AN2586 — see §Verification).
- **Fix:** connect the pins you will use (C2–C4 above), then place no-connect flags on the rest, or better bring
  spare GPIO to 2.54 mm headers so the board is usable as a dev board.

---

## MEDIUM

### M1. Dangling empty label inside R1's body (ERC error) — **fixed on this branch**
- **Where:** `(label "" (at 123.19 68.58 0))` previously at `STM32_Board.kicad_sch:2692-2701`; R1 is at
  (120.65, 68.58) rotated 90°, pins at x = 116.84 and 124.46, so x = 123.19 touches no wire or pin.
- **Evidence:** script output before the fix listed `<EMPTY LABEL> [0] <-- LABEL WITH NO PINS`; project ERC
  severity `label_dangling = "error"`.
- **Fix applied:** label removed (commit on `claude/design-review`). Netlist unchanged otherwise (diff is the
  10-line label block only).

### M2. No reset push-button and no reset access
- **Where:** net `NRST` = U1.7 + C9 100 nF only.
- **Evidence:** the F103 has an internal NRST pull-up (RPU ≈ 40 kΩ typ, DS5319 — see §Verification), so the
  circuit *works*, and 100 nF matches AN2586. But with no button or header pin on NRST, a hung board can only be
  reset by power-cycling, and SWD "connect under reset" is impossible.
- **Fix:** add a momentary switch NRST→GND next to C9, and route NRST to the SWD header (C4). An external 10 kΩ
  pull-up is optional; AN2586 shows the internal pull-up as sufficient.

### M3. BOOT0 switch is only useful with a UART1 header; BOOT1 (PB2) left floating
- **Where:** `BOOT0` = U1.44 ← R1 10 kΩ ← SW1 common (`SW_BOOT0`); SW1.1 = GND, SW1.3 = +3.3V. U1.20 PB2/BOOT1
  unconnected.
- **Evidence:** correct topology and value (AN2586 recommends a 10 kΩ pull-down/up on BOOT0). With BOOT0 = 1 the
  boot mode depends on BOOT1 (PB2): BOOT1 = 0 → system memory (bootloader), BOOT1 = 1 → SRAM. BOOT1 is sampled
  at reset; floating is a risk. Nothing in the schematic can talk to the bootloader (no USART1 header, no USB
  DFU on F103).
- **Fix:** pull PB2/BOOT1 to GND through 10 kΩ (or tie through a 100 kΩ, it has no other use yet); add a USART1
  header (PA9 TX, PA10 RX, GND) or drop the switch and program over SWD only. Note the switch position silkscreen
  "0 = flash / 1 = bootloader".

### M4. Ferrite bead FB1 under-specified ("120R")
- **Where:** FB1 value `120R`, `STM32_Board.kicad_sch:4243`, no footprint, no part number.
- **Evidence:** a bead is specified by impedance at 100 MHz, DC resistance and rated current, not as a resistor
  value. VDDA current on the F103 is a few mA, so almost any 0603/0805 bead works, but "120R" could be ordered as
  a 120 Ω resistor, which would drop ~0.5 V at 4 mA and starve VDDA.
- **Fix:** value "120Ω@100MHz" with MPN (e.g. Murata BLM18AG121SN1D, 0603, 120 Ω, 0.5 A, 0.1 Ω DCR). Keep
  C6 10 nF + C7 1 µF right at pin 9 (matches AN2586's VDDA recommendation).

### M5. Capacitor voltage/dielectric and the 10 µF bulk not specified
- **Where:** C1–C9 values only ("100n", "10u", "1u", "10n").
- **Fix:** add fields: 100 nF/10 nF X7R 16–50 V 0603; 1 µF X5R/X7R ≥10 V 0603; 10 µF X5R ≥6.3 V 0805 (or two
  4.7 µF). AN2586 asks for one 100 nF per VDD pin plus a 4.7 µF (or larger) bulk — present (C1–C4, C5).

### M6. README overstates status
- **Where:** `README.md` "USB connectivity", "SWD debug interface", "schematic complete".
- **Fix:** list these as planned until C2–C4 are drawn.

---

## LOW

### L1. VBAT tied to +3.3V — correct, but give it its own 100 nF and note it
- U1.1 VBAT on `+3.3V`. AN2586: when no backup battery is used, connect VBAT to VDD (with the usual 100 nF).
  C4 can serve; place it at pin 1. Correct as drawn; nothing to change electrically.

### L2. LSE (32.768 kHz) not provided; PC14/PC15 free
- Only matters if the RTC is needed. If so: 32.768 kHz crystal with CL 6–12.5 pF, load caps per the same formula,
  and keep the LSE away from the HSE and switching nodes.

### L3. No status LED or user button
- Convention for a "minimum viable board": LED on PC13 (sink, via 1 kΩ) and a user button. Purely a usability item.

### L4. Label font sizes inconsistent (0.889 / 1.143 / 1.27 mm) and labels used where a wire would do
- `BOOT0`, `SW_BOOT0` 0.889 mm; `NRST` 1.27 mm. Cosmetic; set all to 1.27 mm.

### L5. Symbol pin types: VSS pins 35 and 47 are `passive` in the KiCad library symbol
- Normal for the stacked KiCad symbol (`STM32_Board.kicad_sch` lib_symbols); all three VSS and VSSA are on GND in
  the netlist, so this is informational only.

### L6. `fabrication/`, `datasheets/`, `images/` folders are empty
- Add DS5319, AN2586, the crystal and regulator datasheets to `datasheets/` so the BOM choices are traceable.

---

## What is correct (verified against the files; datasheet cross-checks in §Verification)

| Item | Drawn | Status |
|---|---|---|
| Footprint for U1 | `Package_QFP:LQFP-48_7x7mm_P0.5mm` | Matches STM32F103C8T6 (LQFP48 7×7 mm, 0.5 mm pitch) |
| VDD decoupling | C1, C2, C3, C4 = 100 nF on `+3.3V`/GND; C5 = 10 µF; C8 = 1 µF | One 100 nF per VDD pin (24, 36, 48) + VBAT, plus bulk — matches AN2586 |
| VDDA filter | FB1 → `+3.3VA`; C6 10 nF + C7 1 µF to GND; U1.9 VDDA, U1.8 VSSA → GND | Matches AN2586 10 nF + 1 µF recommendation |
| VBAT | U1.1 on `+3.3V` | Correct when no battery |
| NRST | U1.7 + C9 100 nF to GND | Matches AN2586; internal pull-up present |
| BOOT0 | U1.44 ← 10 kΩ ← SPDT common; A = GND, C = +3.3V | Correct topology and value |
| Pin numbering of the embedded symbol | 48 pins, VBAT 1, NRST 7, VSSA 8, VDDA 9, VSS 23/35/47, VDD 24/36/48, BOOT0 44, PA11/12 = 32/33, PA13/14 = 34/37 | Matches DS5319 LQFP48 pinout (see §Verification) |

## Verification log (primary sources)

Filled in from the reviewers' document reads; anything not listed here is UNVERIFIED.

