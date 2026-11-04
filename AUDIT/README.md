# AUDIT — design review of STM32_Board (started 2026-11-04 21:45 UTC)

Review branch: `claude/design-review`. Final report: [DESIGN_REVIEW.md](DESIGN_REVIEW.md).

## What is in the repository (survey)

| Item | Finding |
|---|---|
| EDA tool | KiCad 9 (`kicad_sch` version 20250114, generator 9.0; `kicad_pcb` version 20241229) |
| MCU | `MCU_ST_STM32F1:STM32F103C8Tx`, value **STM32F103C8T6**, footprint `Package_QFP:LQFP-48_7x7mm_P0.5mm` |
| Schematic | `STM32_Board/STM32_Board.kicad_sch` — 1 sheet, 13 real components: U1, C1–C9, FB1, R1, SW1 |
| PCB | `STM32_Board/STM32_Board.kicad_pcb` — **empty** (0 footprints, 0 tracks, 0 nets) |
| Firmware | none in the repository |
| Power input | none drawn — `+3.3V` and `+3.3VA` power symbols only, no regulator, connector or USB |
| README claims | "USB connectivity", "SWD debug interface" — neither is in the schematic yet |

## Plan

1. Re-runnable checks (`AUDIT/scripts/`): schematic netlist/connectivity extraction without KiCad
   (`sch_netlist.py`), outputs in `AUDIT/out/`.
   `kicad-cli` ERC was attempted: only KiCad 7.0.11 is installable from Ubuntu 24.04 apt and it cannot
   load KiCad 9 files; the KiCad 9 PPA could not be added in this sandbox. ERC-equivalent checks are
   therefore done by the script (unconnected pins, single-pin nets, empty labels, missing footprints).
2. MCU integration review against ST DS5319 (STM32F103x8/xB datasheet) and AN2586 (getting started with
   STM32F10xxx hardware development): VDD/VSS decoupling, VDDA/VSSA filtering, VBAT, NRST, BOOT0, OSC pins,
   USB requirements, SWD.
3. Power tree, interfaces, footprints/DFM: mostly "missing" findings at this stage; each listed with the exact
   change needed.
4. Deliverable: `AUDIT/DESIGN_REVIEW.md` ranked CRITICAL / HIGH / MEDIUM / LOW, every item with reference
   designator, net or pin, evidence (file:line or script output) and fix.

## Re-running the checks

```
python3 -I AUDIT/scripts/sch_netlist.py STM32_Board/STM32_Board.kicad_sch --json AUDIT/out/netlist.json
```
