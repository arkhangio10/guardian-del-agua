# Training Data Sources

## loreto_historical.csv

**Status: SYNTHETIC — for hackathon MVP only.**

The 50 rows in this file are synthetically generated values calibrated to realistic
ranges based on published OEFA enforcement records and academic literature on Amazon
oil spill impacts.

Real sources to replace this file with before production use:
- OEFA resoluciones de sanción (2014–2024): https://www.oefa.gob.pe/resoluciones
- OSINERGMIN incidentes de hidrocarburos: https://www.osinergmin.gob.pe
- PUINAMUDT community health reports (2013–2022)
- PNAS: "Repeated oil spills in Amazonian rivers" (2016)
- Ministry of Health (MINSA) epidemiological bulletins for Loreto

Feature ranges used (based on real Loreto conditions):
- volume_barrels: 100–5000 bbl (typical NorPeruano spill range per OEFA records)
- river_flow_m3s: 700–2000 m³/s (Marañón/Tigre/Corrientes seasonal range)
- biodiversity_index: 0.72–0.90 (RAISG Amazon biodiversity scoring)
- pop_density_per_km2: 3–20 (Loreto census, INEI 2017)

## norperuana.geojson

**Status: APPROXIMATE BOUNDING BOXES — not real MINEM shapefile data.**

The polygon coordinates are rectangular bounding boxes that approximate the
NorPeruano pipeline corridor in Loreto, Peru. They correctly place the pipeline
within the right watershed but do not reflect the actual concession boundaries.

Real shapefile source:
- MINEM SIDEMCAT portal: https://sidemcat.minem.gob.pe
- GEOCATMIN (INGEMMET): https://geocatmin.ingemmet.gob.pe
- ArcGIS format, EPSG:4326, requires registration to download

Operator names, concession IDs, sanction counts, and OSINERGMIN registry numbers
are from publicly available records cited in the project documentation.
