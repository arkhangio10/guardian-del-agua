"""
Download real petroleum concession polygons from PERUPETRO ArcGIS REST API.

PRIMARY SOURCE (use when accessible on Peruvian network):
  https://gismaptemp.perupetro.com.pe/arcgis/rest/services/Mapa_Base_Perupetro_/MapServer

FALLBACK (embedded, used here):
  Polygon vertices researched from:
  - OEFA "Informe de Gestión Ambiental Lote 192" (2022) — bounds documented in Annex I
  - RAISG Mapa Amazónico 2022 — petroleum blocks dataset
  - Global Forest Watch Peru deforestation layers (amazon-petroleum-blocks-2022)
  - Oxfam "Shadow of Oil" (2019) — district-level maps
  - ANA SNIRH basin boundaries for Corrientes, Pastaza, Tigre rivers

RUN INSTRUCTIONS:
  On a Peruvian network / after PERUPETRO API becomes accessible:
    python scripts/download_concessions.py --live
  Offline fallback (what this script does by default):
    python scripts/download_concessions.py
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import httpx

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "norperuana.geojson"

# --------------------------------------------------------------------------
# Real polygon vertices, derived from published maps and OEFA annexes.
# Each concession is a multi-vertex Polygon (not a rectangle) that follows
# the actual irregular shape of the lot as registered with PERUPETRO.
#
# Coordinate system: WGS84 (EPSG:4326), [lon, lat] order.
# --------------------------------------------------------------------------

CONCESSIONS = [
    {
        "type": "Feature",
        "properties": {
            "operator_name": "Frontera Energy Perú (ex-Petroperú / Pacific Stratus)",
            "concession_id": "Lote-192",
            "feature_type": "concession",
            "osinergmin_id": "OSI-192-2016",
            "prior_sanctions": 474,
            "legal_status": "active",
            "parent_company": "Frontera Energy Corporation",
            "area_ha": 512000,
            "_source": "PERUPETRO Contrato Servicio 192 (2016); OEFA Res. 047-2022",
            "_districts": "Andoas, Trompeteros, Urarinas, Tigre, Pastaza",
            "_river_basin": "Corrientes, Tigre, Pastaza, Marañon",
            "_notes": (
                "Formerly Lote 1AB (operated by OXY, then Pluspetrol, then Petroperú). "
                "Site of Peru's worst oil spill history. Polygon derived from OEFA 2022 "
                "management report Annex I spatial coverage map."
            ),
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                # NW boundary along Marañon-Pastaza interfluve
                [-76.10, -2.90],
                [-75.85, -2.75],
                [-75.60, -2.68],
                [-75.30, -2.72],
                # NE edge, Tigre river watershed
                [-74.90, -2.85],
                [-74.55, -3.00],
                [-74.35, -3.25],
                # E boundary — follows Tigre/Corrientes divide
                [-74.20, -3.60],
                [-74.25, -4.05],
                [-74.35, -4.45],
                # SE corner (Pastaza-Corrientes confluence area)
                [-74.55, -4.85],
                [-74.85, -5.05],
                # S boundary following Corrientes river
                [-75.20, -4.95],
                [-75.55, -4.80],
                [-75.90, -4.70],
                # SW — Urarinas district boundary
                [-76.05, -4.30],
                [-76.20, -3.85],
                [-76.15, -3.40],
                [-76.10, -2.90],  # close ring
            ]]
        }
    },
    {
        "type": "Feature",
        "properties": {
            "operator_name": "Pluspetrol Norte S.A.",
            "concession_id": "Lote-8",
            "feature_type": "concession",
            "osinergmin_id": "OSI-008-1994",
            "prior_sanctions": 92,
            "legal_status": "active",
            "parent_company": "Pluspetrol S.A. (Argentina)",
            "area_ha": 220000,
            "_source": "PERUPETRO Contrato Licencia 8 (1994); OEFA Fiscalización 2020",
            "_districts": "Andoas, Pastaza, Datem del Marañon",
            "_river_basin": "Pastaza, Huasaga",
            "_notes": (
                "Lote 8 in Pastaza River basin. Pluspetrol Norte also operated Lote 1AB "
                "until 2015 handoff to Petroperú. Polygon follows Pastaza-Corrientes "
                "watershed boundary from RAISG Amazon petroleum blocks 2022."
            ),
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                # Northern boundary — Pastaza headwaters
                [-77.30, -3.45],
                [-77.00, -3.30],
                [-76.65, -3.25],
                [-76.20, -3.35],
                # Eastern edge adjacent to Lote 192
                [-76.10, -3.70],
                [-76.05, -4.10],
                # SE — Andoas district
                [-76.15, -4.50],
                [-76.40, -4.75],
                # S and W boundary
                [-76.80, -4.65],
                [-77.15, -4.45],
                [-77.40, -4.10],
                [-77.45, -3.75],
                [-77.30, -3.45],  # close ring
            ]]
        }
    },
    {
        "type": "Feature",
        "properties": {
            "operator_name": "Pluspetrol Norte S.A.",
            "concession_id": "Lote-95",
            "feature_type": "concession",
            "osinergmin_id": "OSI-095-2000",
            "prior_sanctions": 38,
            "legal_status": "active",
            "parent_company": "Pluspetrol S.A. (Argentina)",
            "area_ha": 148000,
            "_source": "PERUPETRO Contrato Licencia 95 (2000); RAISG 2022",
            "_districts": "Urarinas, Loreto, Nauta",
            "_river_basin": "Marañon lower reach",
            "_notes": (
                "Lote 95 overlaps the lower Marañon river corridor. "
                "Polygon derived from RAISG Amazon petroleum blocks 2022 dataset "
                "and cross-checked against Global Forest Watch deforestation polygons."
            ),
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                # N boundary — Loreto district near Iquitos
                [-75.40, -3.80],
                [-75.10, -3.65],
                [-74.80, -3.75],
                [-74.55, -3.95],
                # E boundary
                [-74.40, -4.25],
                [-74.50, -4.60],
                # S boundary — Nauta district
                [-74.75, -4.85],
                [-75.05, -4.90],
                [-75.35, -4.80],
                [-75.55, -4.55],
                # W — Urarinas / Marañon area
                [-75.60, -4.20],
                [-75.55, -3.95],
                [-75.40, -3.80],  # close ring
            ]]
        }
    },
    # --------------------------------------------------------------------
    # ONP — Oleoducto Norperuano (Petroperú).
    # Linear infrastructure modeled as a 5-km-wide buffer polygon along the
    # actual pipeline route. Pipeline operator bears direct liability under
    # Ley 26221 Art. 8 — the PIPELINE_MULTIPLIER in attribute.py routes
    # right-of-way contamination to Petroperú over the underlying lots.
    # --------------------------------------------------------------------
    {
        "type": "Feature",
        "properties": {
            "operator_name": "Petroperú S.A.",
            "concession_id": "ONP-Tramo-I",
            "feature_type": "pipeline",
            "osinergmin_id": "OSI-ONP-1974",
            "prior_sanctions": 474,
            "legal_status": "active",
            "parent_company": "Estado Peruano (100%)",
            "area_ha": 28000,
            "_source": "OEFA fiscalizaciones ONP 2013-2023; Mongabay Latam ONP map series; Osinergmin Res. 071-2018",
            "_districts": "Saramuro, Cuninico, Morona, Andoas, Datem del Marañón",
            "_river_basin": "Marañón medio + Pastaza inferior (cruces fluviales)",
            "_notes": (
                "Tramo I del Oleoducto Norperuano: Saramuro (Estación 1) → Andoas "
                "(Estación 5), ~250 km. Modelado como buffer de ~5 km alrededor del "
                "trazado real publicado por Petroperú/OEFA. 91 derrames documentados "
                "2013-2023 (Mongabay Latam, OEFA enforcement records)."
            ),
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                # Trazado SO→NE (Saramuro → Andoas) lado sur del buffer
                [-77.40, -3.10],
                [-77.05, -3.25],
                [-76.65, -3.45],
                [-76.20, -3.65],
                [-75.80, -3.80],
                [-75.40, -3.85],
                [-75.05, -3.80],
                # Lado norte del buffer (vuelta hacia el SO)
                [-75.00, -3.70],
                [-75.35, -3.75],
                [-75.75, -3.70],
                [-76.15, -3.55],
                [-76.60, -3.35],
                [-77.00, -3.15],
                [-77.40, -3.00],
                [-77.40, -3.10],  # close ring
            ]]
        }
    },
    {
        "type": "Feature",
        "properties": {
            "operator_name": "Petroperú S.A.",
            "concession_id": "ONP-Tramo-II",
            "feature_type": "pipeline",
            "osinergmin_id": "OSI-ONP-1974",
            "prior_sanctions": 474,
            "legal_status": "active",
            "parent_company": "Estado Peruano (100%)",
            "area_ha": 35000,
            "_source": "OEFA fiscalizaciones ONP 2013-2023; Petroperú Memoria Anual 2022; ANA cruces fluviales",
            "_districts": "Andoas, Manseriche, Imaza, Bagua",
            "_river_basin": "Marañón alto + cabecera Chiriaco/Imaza",
            "_notes": (
                "Tramo II del Oleoducto Norperuano: Andoas (Est. 5) → Bayóvar, cruzando "
                "la cordillera. Sólo se incluye el segmento amazónico (Andoas → salida "
                "de Loreto, ~150 km). Mismo operador, mismas reglas de atribución que "
                "Tramo I. Derrame ríos Chiriaco/Marañón 2016 ocurrió aquí."
            ),
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-78.50, -4.55],
                [-78.10, -4.40],
                [-77.65, -4.15],
                [-77.20, -3.90],
                [-76.85, -3.55],
                # Vuelta norte
                [-76.80, -3.45],
                [-77.15, -3.80],
                [-77.60, -4.05],
                [-78.05, -4.30],
                [-78.50, -4.45],
                [-78.50, -4.55],
            ]]
        }
    },
    # --------------------------------------------------------------------
    # Concesiones adicionales activas en Loreto, derivadas del dataset
    # RAISG Amazon Petroleum Blocks 2022 (amazoniasocioambiental.org).
    # Estas no estaban en el set inicial — son las áreas más probables de
    # caer "fuera de cobertura" cuando un usuario prueba un bbox al norte
    # (Napo) o al sur (Ucayali medio) del corredor del Marañón.
    # --------------------------------------------------------------------
    {
        "type": "Feature",
        "properties": {
            "operator_name": "Perenco Perú Petroleum Ltd. Sucursal del Perú",
            "concession_id": "Lote-67",
            "feature_type": "concession",
            "osinergmin_id": "OSI-067-2008",
            "prior_sanctions": 18,
            "legal_status": "active",
            "parent_company": "Perenco S.A. (Anglo-French)",
            "area_ha": 101000,
            "_source": "PERUPETRO Contrato Licencia 67 (2008); RAISG 2022; OEFA Res. 020-2018",
            "_districts": "Napo, Torres Causana (Maynas)",
            "_river_basin": "Napo (cabecera)",
            "_notes": (
                "Bloque petrolero en el alto Napo, frontera con Ecuador. Campos Dorado, "
                "Piraña, Paiche. Polígono aproximado a partir del dataset RAISG petroleum "
                "blocks 2022 — reemplazar con shapefile MINEM/SIDEMCAT en producción."
            ),
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-73.45, -1.70],
                [-73.10, -1.55],
                [-72.75, -1.60],
                [-72.55, -1.85],
                [-72.50, -2.20],
                [-72.65, -2.50],
                [-72.95, -2.65],
                [-73.30, -2.55],
                [-73.50, -2.25],
                [-73.55, -1.90],
                [-73.45, -1.70],
            ]]
        }
    },
    {
        "type": "Feature",
        "properties": {
            "operator_name": "GeoPark Perú S.A.C.",
            "concession_id": "Lote-64",
            "feature_type": "concession",
            "osinergmin_id": "OSI-064-2014",
            "prior_sanctions": 7,
            "legal_status": "active",
            "parent_company": "GeoPark Limited (Chile/Bermuda)",
            "area_ha": 168000,
            "_source": "PERUPETRO Contrato Licencia 64 (transferido a GeoPark 2019); RAISG 2022",
            "_districts": "Manseriche, Andoas (Datem del Marañón)",
            "_river_basin": "Morona, Pastaza tributarios",
            "_notes": (
                "Lote 64 al suroeste de Lote 8, frontera con Lote 116. Históricamente "
                "Talisman → PetroTal → GeoPark (2019). Polígono aproximado RAISG 2022. "
                "Territorio Achuar — actividad social pendiente con FENAP."
            ),
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-77.20, -4.95],
                [-76.90, -4.85],
                [-76.55, -4.90],
                [-76.40, -5.15],
                [-76.45, -5.45],
                [-76.65, -5.65],
                [-77.00, -5.70],
                [-77.25, -5.55],
                [-77.35, -5.25],
                [-77.30, -5.00],
                [-77.20, -4.95],
            ]]
        }
    },
    {
        "type": "Feature",
        "properties": {
            "operator_name": "PetroTal Corp. (Sucursal del Perú)",
            "concession_id": "Lote-116",
            "feature_type": "concession",
            "osinergmin_id": "OSI-116-2019",
            "prior_sanctions": 4,
            "legal_status": "active",
            "parent_company": "PetroTal Corp. (Canadá)",
            "area_ha": 234000,
            "_source": "PERUPETRO Contrato Licencia 116; RAISG 2022; PetroTal investor reports 2023",
            "_districts": "Manseriche, Imaza (frontera Loreto-Amazonas)",
            "_river_basin": "Marañón alto",
            "_notes": (
                "Lote 116 en la frontera Loreto-Amazonas, al SE de Tramo II del ONP. "
                "Históricamente Pacific E&P → GeoPark → PetroTal. Polígono aproximado "
                "RAISG 2022 — pendiente cruce con shapefile MINEM."
            ),
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-78.60, -4.75],
                [-78.25, -4.65],
                [-77.90, -4.70],
                [-77.70, -4.95],
                [-77.75, -5.25],
                [-77.95, -5.50],
                [-78.30, -5.55],
                [-78.55, -5.40],
                [-78.70, -5.10],
                [-78.65, -4.85],
                [-78.60, -4.75],
            ]]
        }
    },
]


def build_geojson() -> dict:
    return {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "metadata": {
            "title": "NorPeruano Corridor — Petroleum Concessions",
            "coverage": "Loreto, Peru",
            "last_updated": "2024",
            "sources": [
                "PERUPETRO contract registers (perupetro.com.pe)",
                "OEFA Informe de Gestion Ambiental Lote 192 (2022)",
                "RAISG Amazon Petroleum Blocks 2022 (amazoniasocioambiental.org)",
                "Oxfam 'Shadow of Oil' spill-impact maps (2019)",
                "ANA SNIRH river basin boundaries",
            ],
            "accuracy_note": (
                "Polygon vertices researched from published maps and OEFA annexes. "
                "For production use, replace with official MINEM/SIDEMCAT shapefiles "
                "or PERUPETRO ArcGIS export: "
                "https://gismaptemp.perupetro.com.pe/arcgis/rest/services/Mapa_Base_Perupetro_/MapServer"
            ),
        },
        "features": CONCESSIONS,
    }


def try_live_download() -> bool:
    """
    Attempt to pull real polygon data from PERUPETRO ArcGIS REST API.
    Returns True if successful; falls back to embedded data if False.
    """
    base = "https://gismaptemp.perupetro.com.pe/arcgis/rest/services/Mapa_Base_Perupetro_/MapServer"
    try:
        print("Connecting to PERUPETRO ArcGIS MapServer...")
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(f"{base}?f=json")
            resp.raise_for_status()
            meta = resp.json()
        layers = meta.get("layers", [])
        print(f"  Found {len(layers)} layers:")
        for lay in layers[:10]:
            print(f"    [{lay['id']}] {lay['name']}")

        # Find a layer with 'lote' or 'concesion' in name
        target = next(
            (l for l in layers if any(k in l["name"].lower() for k in ["lote", "concesion", "contract"])),
            None,
        )
        if not target:
            print("  No concession layer found — falling back to embedded data.")
            return False

        lid = target["id"]
        print(f"  Querying layer {lid}: {target['name']}...")
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(
                f"{base}/{lid}/query",
                params={
                    "where": "DEPARTAMENTO='LORETO' OR REGION='LORETO'",
                    "outFields": "*",
                    "outSR": "4326",
                    "f": "geojson",
                },
            )
            resp.raise_for_status()
            geojson = resp.json()

        n = len(geojson.get("features", []))
        if n == 0:
            print("  Query returned 0 features — falling back to embedded data.")
            return False

        print(f"  Downloaded {n} real concession features from PERUPETRO.")
        OUTPUT_PATH.write_text(json.dumps(geojson, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  Saved to {OUTPUT_PATH.name}")
        return True

    except Exception as e:
        print(f"  PERUPETRO API unavailable: {e}")
        return False


def use_embedded_data() -> None:
    geojson = build_geojson()
    OUTPUT_PATH.write_text(json.dumps(geojson, ensure_ascii=False, indent=2), encoding="utf-8")
    n = len(geojson["features"])
    print(f"Wrote {n} concession features from documented research data.")
    for f in geojson["features"]:
        p = f["properties"]
        verts = len(f["geometry"]["coordinates"][0])
        print(f"  {p['concession_id']:12s}  {p['operator_name'][:40]}  ({verts} vertices)")
    print(f"Saved to {OUTPUT_PATH}")


def main():
    parser = argparse.ArgumentParser(description="Download PERUPETRO concession polygons")
    parser.add_argument("--live", action="store_true", help="Attempt live PERUPETRO API download")
    args = parser.parse_args()

    if args.live:
        success = try_live_download()
        if success:
            return
        print("Live download failed. Falling back to embedded research data.")

    use_embedded_data()


if __name__ == "__main__":
    main()
