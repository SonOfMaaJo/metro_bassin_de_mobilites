#!/usr/bin/env bash
#
# build_communes_osm.sh
#
# Fusionne un ou plusieurs fichiers .osm.pbf puis les restreint aux communes listées dans un
# CSV simplifie a 2 colonnes : le code commune officiel (INSEE ou AGS, voir --insee-column,
# defaut "COMMUNE") et le nom de la commune (defaut "NCC", non utilise pour le filtrage --
# uniquement le code compte -- garde pour la lisibilite/maintenance du fichier). Toute colonne
# supplementaire est ignoree, donc un CSV avec plus de colonnes (ex. BASSIN_MOBILITE_GE_SGP2026.xlsx
# d'origine : REGION, DEPT, CANTVILLE, COMMUNE, NCC) fonctionne aussi.
#
# Communes transfrontalieres : le matching accepte aussi bien les codes INSEE francais
# (5 chiffres, tag OSM `ref:INSEE`) que les codes AGS allemands ("Amtlicher Gemeindeschluessel",
# 8 chiffres, tag OSM `de:amtlicher_gemeindeschluessel`) -- il suffit d'ajouter les codes AGS des
# communes allemandes dans la meme colonne code du CSV, et de fournir en --pbf un extrait OSM
# qui couvre aussi le cote allemand (ex. extrait Geofabrik "Baden-Wuerttemberg" ou
# "Rheinland-Pfalz" en plus de l'extrait francais).
#
# Usage interactif (sans argument, le script pose les questions) :
#   ./build_communes_osm.sh
#
# Usage non-interactif :
#   ./build_communes_osm.sh --csv communes.csv --pbf a.osm.pbf b.osm.pbf --output bassin.osm.pbf
#
# Options :
#   --csv FILE            Fichier CSV des communes (obligatoire, demande si absent)
#   --pbf FILE [FILE...]  Un ou plusieurs fichiers .osm.pbf source (obligatoire, demande si absent)
#   --output FILE         Fichier .osm.pbf de sortie (obligatoire, demande si absent)
#   --insee-column NAME   Nom de la colonne code commune (INSEE et/ou AGS) dans le CSV
#                         (defaut: COMMUNE)
#   --buffer METERS       Marge autour du contour des communes avant decoupe, en metres
#                         (defaut: 10000)
#   --crs EPSG            CRS utilise pour les calculs de surface / le polygone de sortie
#                         (defaut: EPSG:2154)
#   --strategy STRAT      Strategie `osmium extract` (defaut: smart)
#   -y, --yes             Ne pose aucune question de confirmation
#   -h, --help            Affiche cette aide
#
set -euo pipefail

# ---------------------------------------------------------------------------
# Valeurs par defaut / etat
# ---------------------------------------------------------------------------
CSV_FILE=""
PBF_FILES=()
OUTPUT_FILE=""
INSEE_COLUMN="COMMUNE"
BUFFER_M=10000
CRS="EPSG:2154"
STRATEGY="smart"
ASSUME_YES=0

WORKDIR="$(mktemp -d /tmp/build_communes_osm.XXXXXX)"
trap 'rm -rf "$WORKDIR"' EXIT

log()  { printf '\033[1;34m[build_communes_osm]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[build_communes_osm][WARN]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[build_communes_osm][ERREUR]\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
    sed -n '2,38p' "$0" | sed 's/^# \{0,1\}//'
}

# ---------------------------------------------------------------------------
# Parsing des arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --csv)
            CSV_FILE="$2"; shift 2 ;;
        --pbf)
            shift
            while [[ $# -gt 0 && "$1" != --* ]]; do
                PBF_FILES+=("$1"); shift
            done ;;
        --output)
            OUTPUT_FILE="$2"; shift 2 ;;
        --insee-column)
            INSEE_COLUMN="$2"; shift 2 ;;
        --buffer)
            BUFFER_M="$2"; shift 2 ;;
        --crs)
            CRS="$2"; shift 2 ;;
        --strategy)
            STRATEGY="$2"; shift 2 ;;
        -y|--yes)
            ASSUME_YES=1; shift ;;
        -h|--help)
            usage; exit 0 ;;
        *)
            die "Argument inconnu : $1 (voir --help)" ;;
    esac
done

# ---------------------------------------------------------------------------
# 1. Verification / installation des dependances
# ---------------------------------------------------------------------------
detect_pkg_manager() {
    if command -v apt-get >/dev/null 2>&1; then echo "apt"; return; fi
    if command -v dnf >/dev/null 2>&1; then echo "dnf"; return; fi
    if command -v yum >/dev/null 2>&1; then echo "yum"; return; fi
    if command -v pacman >/dev/null 2>&1; then echo "pacman"; return; fi
    if command -v brew >/dev/null 2>&1; then echo "brew"; return; fi
    echo "none"
}

install_osmium_tool() {
    local mgr; mgr="$(detect_pkg_manager)"
    warn "osmium-tool introuvable, tentative d'installation via '$mgr'..."
    case "$mgr" in
        apt)
            apt-get update -y && apt-get install -y osmium-tool ;;
        dnf)
            dnf install -y osmium-tool ;;
        yum)
            yum install -y osmium-tool ;;
        pacman)
            pacman -Sy --noconfirm osmium-tool ;;
        brew)
            brew install osmium-tool ;;
        *)
            die "Aucun gestionnaire de paquets reconnu (apt/dnf/yum/pacman/brew). \
Installe 'osmium-tool' manuellement puis relance ce script." ;;
    esac
}

# Environnement virtuel dedie, reutilise d'un run a l'autre (evite de reinstaller a chaque
# execution, et contourne les python "externally-managed" qui refusent `pip install` global).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.build_communes_osm_venv"
PYTHON_BIN="python3"

create_venv() {
    if ! python3 -m venv "$VENV_DIR" 2>"$WORKDIR/venv_err.log"; then
        warn "Echec de creation du venv, tentative d'installation de python3-venv..."
        local mgr; mgr="$(detect_pkg_manager)"
        case "$mgr" in
            apt) apt-get update -y && apt-get install -y python3-venv python3-full ;;
            dnf) dnf install -y python3-virtualenv ;;
            yum) yum install -y python3-virtualenv ;;
            pacman) pacman -Sy --noconfirm python-virtualenv ;;
            brew) : ;; # venv fait partie du python de brew
            *) die "Impossible de creer un environnement virtuel Python (module venv absent)." ;;
        esac
        python3 -m venv "$VENV_DIR" || die "Impossible de creer l'environnement virtuel : $(cat "$WORKDIR/venv_err.log")"
    fi
}

ensure_python_packages() {
    if python3 -c "import osmium, geopandas" >/dev/null 2>&1; then
        PYTHON_BIN="python3"
        log "  modules Python osmium/geopandas : OK (python3 systeme)"
        return
    fi
    if [[ -x "$VENV_DIR/bin/python3" ]] && "$VENV_DIR/bin/python3" -c "import osmium, geopandas" >/dev/null 2>&1; then
        PYTHON_BIN="$VENV_DIR/bin/python3"
        log "  modules Python osmium/geopandas : OK (venv existant : $VENV_DIR)"
        return
    fi
    warn "Modules Python 'osmium'/'geopandas' absents, creation d'un environnement virtuel dedie : $VENV_DIR"
    create_venv
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip
    "$VENV_DIR/bin/pip" install --quiet osmium geopandas \
        || die "Echec de l'installation de osmium/geopandas dans l'environnement virtuel. \
Installe-les manuellement ($VENV_DIR/bin/pip install osmium geopandas) puis relance ce script."
    PYTHON_BIN="$VENV_DIR/bin/python3"
    "$PYTHON_BIN" -c "import osmium, geopandas" >/dev/null 2>&1 \
        || die "Les modules restent indisponibles apres installation dans le venv."
    log "  modules Python osmium/geopandas : OK (nouveau venv : $VENV_DIR)"
}

check_dependencies() {
    log "Verification des dependances..."

    if ! command -v python3 >/dev/null 2>&1; then
        die "python3 est introuvable sur ce systeme. Installe-le manuellement puis relance."
    fi

    if ! command -v osmium >/dev/null 2>&1; then
        install_osmium_tool
        command -v osmium >/dev/null 2>&1 || die "osmium reste introuvable apres tentative d'installation."
    fi
    log "  osmium-tool : $(osmium --version 2>&1 | head -n1)"

    ensure_python_packages
}

# ---------------------------------------------------------------------------
# 2. Collecte interactive des entrees manquantes
# ---------------------------------------------------------------------------
prompt_csv() {
    while [[ -z "$CSV_FILE" || ! -f "$CSV_FILE" ]]; do
        read -r -p "Chemin du fichier CSV des communes (format BASSIN_MOBILITE_GE_SGP2026) : " CSV_FILE
        [[ -f "$CSV_FILE" ]] || warn "Fichier introuvable : $CSV_FILE"
    done
}

prompt_pbf_files() {
    while [[ ${#PBF_FILES[@]} -eq 0 ]]; do
        read -r -p "Fichier(s) .osm.pbf source, separes par des espaces : " -a input
        for f in "${input[@]}"; do
            if [[ -f "$f" ]]; then
                PBF_FILES+=("$f")
            else
                warn "Fichier introuvable, ignore : $f"
            fi
        done
        [[ ${#PBF_FILES[@]} -gt 0 ]] || warn "Aucun fichier valide fourni, recommence."
    done
}

prompt_output() {
    while [[ -z "$OUTPUT_FILE" ]]; do
        read -r -p "Fichier .osm.pbf de sortie (chemin complet) : " OUTPUT_FILE
    done
}

confirm() {
    [[ "$ASSUME_YES" -eq 1 ]] && return 0
    local reply
    read -r -p "$1 [o/N] " reply
    [[ "$reply" =~ ^[oOyY] ]]
}

# ---------------------------------------------------------------------------
# 3. Extraction des codes INSEE + polygone du bassin (Python)
# ---------------------------------------------------------------------------
extract_target_area() {
    local csv="$1" insee_col="$2" pbf="$3" crs="$4" buffer="$5"
    local area_geojson="$6" buffered_geojson="$7" missing_txt="$8"

    "$PYTHON_BIN" - "$csv" "$insee_col" "$pbf" "$crs" "$buffer" \
             "$area_geojson" "$buffered_geojson" "$missing_txt" <<'PYEOF'
import csv
import sys

import geopandas as gpd
import osmium
from osmium.filter import TagFilter
from osmium.geom import WKBFactory

csv_path, insee_col, pbf_path, crs, buffer_m, area_out, buffered_out, missing_out = sys.argv[1:9]
buffer_m = float(buffer_m)


def normalize_code(raw: str) -> str:
    """Normalise un code commune : INSEE francais (5 chiffres) ou AGS allemand
    (`Amtlicher Gemeindeschluessel`, 8 chiffres). Les codes non numeriques (ex. Corse 2A/2B)
    sont laisses tels quels."""
    raw = raw.strip()
    if raw.isdigit():
        if len(raw) <= 5:
            return raw.zfill(5)
        if len(raw) <= 8:
            return raw.zfill(8)
    return raw.upper()


# --- Lecture du CSV -> ensemble de codes commune (INSEE et/ou AGS allemand) ---
with open(csv_path, newline="", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    if insee_col not in (reader.fieldnames or []):
        print(f"Colonnes disponibles dans le CSV : {reader.fieldnames}", file=sys.stderr)
        sys.exit(f"Colonne '{insee_col}' absente du CSV.")
    codes = {normalize_code(str(row[insee_col])) for row in reader}

print(f"Codes commune cibles : {len(codes)}")

# --- Lecture des relations admin_level=8 du fichier OSM (fusionne) ---
# On teste plusieurs tags de code officiel selon le pays :
#   - `ref:INSEE` (France)
#   - `de:amtlicher_gemeindeschluessel` (Allemagne, AGS)
#   - `ref` (repli generique pour d'autres pays/conventions)
fab = WKBFactory()
found = {}
for area in (
    osmium.FileProcessor(pbf_path)
    .with_filter(TagFilter(("admin_level", "8")))
    .with_areas()
):
    if not area.is_area():
        continue
    candidates = []
    for tag in ("ref:INSEE", "de:amtlicher_gemeindeschluessel", "ref"):
        value = area.tags.get(tag)
        if value:
            candidates.append(normalize_code(value))
    matched = next((c for c in candidates if c in codes), None)
    if matched is not None:
        found[matched] = (area.tags.get("name"), fab.create_multipolygon(area))

missing = codes - set(found.keys())
print(f"Communes trouvees : {len(found)} / {len(codes)}")
with open(missing_out, "w") as f:
    f.write("\n".join(sorted(missing)))
if missing:
    print(f"ATTENTION : {len(missing)} commune(s) non trouvee(s) (voir {missing_out})", file=sys.stderr)

if not found:
    sys.exit("Aucune commune trouvee : verifie que le(s) fichier(s) .osm.pbf couvrent bien la zone.")

names = [v[0] for v in found.values()]
polys = [v[1] for v in found.values()]
insee_codes = list(found.keys())
gdf = gpd.GeoDataFrame(
    {"insee": insee_codes, "name": names},
    geometry=gpd.GeoSeries.from_wkb(polys, crs="EPSG:4326"),
)
gdf.to_crs(crs, inplace=True)
print(f"Surface de la zone (km2) : {gdf.area.sum() / 1e6:.1f}")
gdf.to_file(area_out, driver="GeoJSON")
print(f"Ecrit : {area_out}")

# --- Polygone bufferise (EPSG:4326) pour la decoupe osmium ---
geom = gdf.union_all().buffer(buffer_m)
buffered = gpd.GeoDataFrame({"id": [1]}, geometry=[geom], crs=crs)
buffered.to_crs("EPSG:4326", inplace=True)
buffered.to_file(buffered_out, driver="GeoJSON")
print(f"Ecrit : {buffered_out}")
PYEOF
}

# ---------------------------------------------------------------------------
# 4. Programme principal
# ---------------------------------------------------------------------------
main() {
    [[ -n "$CSV_FILE" ]] || prompt_csv
    [[ -f "$CSV_FILE" ]] || die "Fichier CSV introuvable : $CSV_FILE"

    [[ ${#PBF_FILES[@]} -gt 0 ]] || prompt_pbf_files
    for f in "${PBF_FILES[@]}"; do
        [[ -f "$f" ]] || die "Fichier .osm.pbf introuvable : $f"
    done

    [[ -n "$OUTPUT_FILE" ]] || prompt_output
    if [[ -f "$OUTPUT_FILE" ]]; then
        confirm "Le fichier de sortie '$OUTPUT_FILE' existe deja, l'ecraser ?" \
            || die "Abandon (fichier de sortie non ecrase)."
    fi

    check_dependencies

    log "CSV               : $CSV_FILE"
    log "Colonne INSEE     : $INSEE_COLUMN"
    log "Fichiers .osm.pbf : ${PBF_FILES[*]}"
    log "Sortie            : $OUTPUT_FILE"
    log "CRS               : $CRS"
    log "Buffer            : ${BUFFER_M} m"
    log "Strategie extract : $STRATEGY"

    # --- Fusion des fichiers .osm.pbf (si plusieurs) ---
    local merged_pbf
    if [[ ${#PBF_FILES[@]} -eq 1 ]]; then
        merged_pbf="${PBF_FILES[0]}"
        log "Un seul fichier .osm.pbf fourni, pas de fusion necessaire."
    else
        merged_pbf="$WORKDIR/merged.osm.pbf"
        log "Fusion de ${#PBF_FILES[@]} fichiers .osm.pbf..."
        if ! osmium merge "${PBF_FILES[@]}" -o "$merged_pbf" --overwrite 2>"$WORKDIR/merge_err.log"; then
            warn "Echec de 'osmium merge' (fichiers probablement non tries), tentative apres tri..."
            local sorted_files=()
            for f in "${PBF_FILES[@]}"; do
                local s="$WORKDIR/$(basename "$f").sorted.osm.pbf"
                osmium sort "$f" -o "$s" --overwrite
                sorted_files+=("$s")
            done
            osmium merge "${sorted_files[@]}" -o "$merged_pbf" --overwrite
        fi
        log "Fusion terminee : $merged_pbf ($(du -h "$merged_pbf" | cut -f1))"
    fi

    # --- Extraction de la zone cible (polygone communes + polygone bufferise) ---
    local area_geojson="$WORKDIR/simulation_area.geojson"
    local buffered_geojson="$WORKDIR/extract_polygon_buffered.geojson"
    local missing_txt="$WORKDIR/missing_communes.txt"
    log "Identification des communes cibles dans les donnees OSM..."
    extract_target_area "$CSV_FILE" "$INSEE_COLUMN" "$merged_pbf" "$CRS" "$BUFFER_M" \
        "$area_geojson" "$buffered_geojson" "$missing_txt"

    # --- Decoupe finale ---
    log "Decoupe du fichier OSM (strategie '$STRATEGY')..."
    osmium extract -p "$buffered_geojson" -s "$STRATEGY" -o "$OUTPUT_FILE" --overwrite "$merged_pbf"

    # --- Copie des artefacts a cote de la sortie ---
    local out_dir out_base
    out_dir="$(dirname "$OUTPUT_FILE")"
    out_base="$(basename "$OUTPUT_FILE" .osm.pbf)"
    cp "$area_geojson" "$out_dir/${out_base}_simulation_area.geojson"
    if [[ -s "$missing_txt" ]]; then
        cp "$missing_txt" "$out_dir/${out_base}_missing_communes.txt"
        warn "Communes non trouvees listees dans : $out_dir/${out_base}_missing_communes.txt"
    fi

    log "Termine."
    log "  Fichier OSM restreint : $OUTPUT_FILE ($(du -h "$OUTPUT_FILE" | cut -f1))"
    log "  Polygone de la zone   : $out_dir/${out_base}_simulation_area.geojson"
    log "  (a utiliser tel quel dans [simulation_area] polygon_file = ... de pymetropolis)"
}

main
