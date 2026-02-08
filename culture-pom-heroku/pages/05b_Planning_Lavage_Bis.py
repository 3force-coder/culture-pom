import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime, date, timedelta

from auth import require_access
from database import get_connection
from streamlit_calendar import fullcalendar_component


st.set_page_config(
    page_title="Planning Lavage Bis",
    page_icon="🧼",
    layout="wide"
)

# ============================================================
# 🔒 RBAC
# ============================================================
require_access("PRODUCTION")


def parse_iso_datetime(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=None)


def get_lignes_lavage():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code, libelle, capacite_th
            FROM lavages_lignes
            WHERE is_active = TRUE
            ORDER BY code
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception as exc:
        st.error(f"❌ Erreur lignes lavage : {exc}")
        return []


def get_jobs_non_planifies(ligne_code):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT j.id, j.code_lot_interne, j.variete, j.quantite_pallox, j.poids_brut_kg,
                   j.temps_estime_heures, j.date_prevue, j.producteur, j.statut_source
            FROM lavages_jobs j
            LEFT JOIN lavages_planning_elements pe ON pe.job_id = j.id
            WHERE j.statut = 'PRÉVU'
              AND j.ligne_lavage = %s
              AND pe.id IS NULL
            ORDER BY j.date_prevue, j.id
        """, (ligne_code,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        for col in ['quantite_pallox', 'poids_brut_kg', 'temps_estime_heures']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
    except Exception as exc:
        st.error(f"❌ Erreur jobs : {exc}")
        return pd.DataFrame()


def get_planning_elements(ligne_code, week_start):
    try:
        week_end = week_start + timedelta(days=6)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                pe.id, pe.type_element, pe.date_prevue, pe.heure_debut, pe.heure_fin,
                pe.duree_minutes, pe.job_id, pe.temps_custom_id, pe.producteur,
                j.code_lot_interne, j.variete, j.statut as job_statut, j.quantite_pallox,
                j.poids_brut_kg, j.temps_estime_heures, j.statut_source,
                tc.libelle as custom_libelle, tc.emoji as custom_emoji
            FROM lavages_planning_elements pe
            LEFT JOIN lavages_jobs j ON pe.job_id = j.id
            LEFT JOIN lavages_temps_customs tc ON pe.temps_custom_id = tc.id
            WHERE pe.date_prevue BETWEEN %s AND %s
              AND pe.ligne_lavage = %s
            ORDER BY pe.date_prevue, pe.heure_debut
        """, (week_start, week_end, ligne_code))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        for col in ['duree_minutes', 'quantite_pallox', 'poids_brut_kg', 'temps_estime_heures']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
    except Exception as exc:
        st.error(f"❌ Erreur planning : {exc}")
        return pd.DataFrame()


def insert_planning_element(job_id, ligne_lavage, start_dt, end_dt, duree_minutes):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        date_prevue = start_dt.date()
        annee, semaine, _ = date_prevue.isocalendar()
        heure_debut = start_dt.time()
        heure_fin = end_dt.time()

        if end_dt <= start_dt:
            cursor.close()
            conn.close()
            return False, "❌ Horaire invalide (fin avant début)."

        if has_conflict(cursor, ligne_lavage, date_prevue, heure_debut, heure_fin):
            cursor.close()
            conn.close()
            return False, "❌ Conflit horaire avec un autre élément."

        cursor.execute("""
            SELECT COALESCE(MAX(ordre_jour), 0) as max_ordre
            FROM lavages_planning_elements
            WHERE date_prevue = %s AND ligne_lavage = %s
        """, (date_prevue, ligne_lavage))
        next_ordre = (cursor.fetchone()['max_ordre'] or 0) + 1

        cursor.execute("""
            SELECT producteur
            FROM lavages_jobs
            WHERE id = %s
        """, (job_id,))
        job_info = cursor.fetchone()
        producteur = job_info.get('producteur') if job_info else None
        created_by = st.session_state.get("username", "system")

        cursor.execute("""
            INSERT INTO lavages_planning_elements (
                type_element, job_id, annee, semaine, date_prevue, ligne_lavage,
                ordre_jour, heure_debut, heure_fin, duree_minutes, created_by, producteur
            ) VALUES ('JOB', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            job_id, annee, semaine, date_prevue, ligne_lavage, next_ordre,
            heure_debut, heure_fin, duree_minutes, created_by, producteur
        ))

        cursor.execute("""
            UPDATE lavages_jobs
            SET date_prevue = %s
            WHERE id = %s
        """, (date_prevue, job_id))

        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Job planifié."
    except Exception as exc:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur planification : {exc}"


def update_planning_element(element_id, start_dt, end_dt):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date_prevue, ligne_lavage
            FROM lavages_planning_elements
            WHERE id = %s
        """, (element_id,))
        current = cursor.fetchone()
        if not current:
            cursor.close()
            conn.close()
            return False, "❌ Élément introuvable."

        date_prevue = start_dt.date()
        heure_debut = start_dt.time()
        heure_fin = end_dt.time()
        duree_minutes = int((end_dt - start_dt).total_seconds() / 60)
        annee, semaine, _ = date_prevue.isocalendar()

        if end_dt <= start_dt:
            cursor.close()
            conn.close()
            return False, "❌ Horaire invalide (fin avant début)."

        ligne_lavage = current.get("ligne_lavage")
        if has_conflict(cursor, ligne_lavage, date_prevue, heure_debut, heure_fin, exclude_id=element_id):
            cursor.close()
            conn.close()
            return False, "❌ Conflit horaire avec un autre élément."

        ordre_jour = None
        if current.get("date_prevue") != date_prevue:
            cursor.execute("""
                SELECT COALESCE(MAX(ordre_jour), 0) as max_ordre
                FROM lavages_planning_elements
                WHERE date_prevue = %s AND ligne_lavage = %s
            """, (date_prevue, ligne_lavage))
            ordre_jour = (cursor.fetchone()['max_ordre'] or 0) + 1

        cursor.execute("""
            UPDATE lavages_planning_elements
            SET date_prevue = %s,
                heure_debut = %s,
                heure_fin = %s,
                duree_minutes = %s,
                annee = %s,
                semaine = %s,
                ordre_jour = COALESCE(%s, ordre_jour)
            WHERE id = %s
        """, (
            date_prevue, heure_debut, heure_fin, duree_minutes,
            annee, semaine, ordre_jour, element_id
        ))

        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Planning mis à jour."
    except Exception as exc:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur mise à jour : {exc}"


def has_conflict(cursor, ligne_lavage, date_prevue, heure_debut, heure_fin, exclude_id=None):
    if not heure_debut or not heure_fin:
        return False

    params = [date_prevue]
    query = """
        SELECT id, heure_debut, heure_fin
        FROM lavages_planning_elements
        WHERE date_prevue = %s
    """

    if ligne_lavage:
        query += " AND ligne_lavage = %s"
        params.append(ligne_lavage)

    if exclude_id:
        query += " AND id <> %s"
        params.append(exclude_id)

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()

    start_minutes = heure_debut.hour * 60 + heure_debut.minute
    end_minutes = heure_fin.hour * 60 + heure_fin.minute

    for row in rows:
        if not row.get("heure_debut") or not row.get("heure_fin"):
            continue
        row_start = row["heure_debut"].hour * 60 + row["heure_debut"].minute
        row_end = row["heure_fin"].hour * 60 + row["heure_fin"].minute
        if start_minutes < row_end and end_minutes > row_start:
            return True
    return False


def build_calendar_events(planning_df):
    events = []
    if planning_df.empty:
        return events

    for _, row in planning_df.iterrows():
        date_prevue = row['date_prevue']
        heure_debut = row['heure_debut']
        heure_fin = row['heure_fin']
        if pd.isna(date_prevue) or pd.isna(heure_debut):
            continue

        start_dt = datetime.combine(date_prevue, heure_debut)
        end_dt = datetime.combine(date_prevue, heure_fin) if pd.notna(heure_fin) else None

        if row['type_element'] == 'CUSTOM':
            title = f"{row.get('custom_emoji', '🔧')} {row.get('custom_libelle', 'Temps custom')}"
            color = "#8e24aa"
        else:
            code_lot = row.get('code_lot_interne') or f"Job #{row.get('job_id')}"
            variete = row.get('variete') or ""
            title = f"{code_lot} - {variete}".strip(" -")
            job_statut = row.get('job_statut')
            if job_statut == "EN_COURS":
                color = "#f57c00"
            elif job_statut == "TERMINÉ":
                color = "#757575"
            else:
                color = "#2e7d32"

        events.append({
            "id": str(row["id"]),
            "title": title,
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat() if end_dt else None,
            "color": color,
            "extendedProps": {
                "planning_id": int(row["id"]),
                "job_id": row.get("job_id"),
                "type_element": row.get("type_element"),
                "variete": row.get("variete"),
                "quantite_pallox": row.get("quantite_pallox"),
                "poids_brut_kg": row.get("poids_brut_kg"),
                "statut_source": row.get("statut_source"),
            }
        })
    return events


st.title("🧼 Planning Lavage Bis")
st.markdown("Version **drag & drop** du planning lavage, sans impacter la page existante.")

lines = get_lignes_lavage()
if not lines:
    st.warning("Aucune ligne de lavage active.")
    st.stop()

line_labels = [f"{line['code']} — {line['libelle']}" for line in lines]
line_map = {f"{line['code']} — {line['libelle']}": line['code'] for line in lines}

col_filters, col_info = st.columns([2, 1])
with col_filters:
    selected_line_label = st.selectbox("Ligne de lavage", line_labels)
    selected_line = line_map[selected_line_label]
with col_info:
    today = date.today()
    week_start_default = today - timedelta(days=today.weekday())
    week_start = st.date_input("Semaine du", value=week_start_default)

planning_df = get_planning_elements(selected_line, week_start)
jobs_df = get_jobs_non_planifies(selected_line)

col_jobs, col_calendar = st.columns([1, 2])

with col_jobs:
    st.subheader("📋 Jobs à planifier")
    st.caption("Glissez un job vers le calendrier.")

    if jobs_df.empty:
        st.success("✅ Aucun job en attente.")
    else:
        draggable_html = "<div id='external-events'>"
        for _, job in jobs_df.iterrows():
            duree_minutes = int(round((job.get('temps_estime_heures') or 1) * 60))
            duration_iso = f"{duree_minutes // 60:02d}:{duree_minutes % 60:02d}:00"
            poids_tonnes = (job.get('poids_brut_kg') or 0) / 1000

            draggable_html += f"""
            <div class="fc-event fc-h-event fc-daygrid-event fc-daygrid-block-event"
                 data-duration="{duration_iso}"
                 data-job-id="{int(job['id'])}"
                 data-code-lot="{job.get('code_lot_interne', '')}"
                 data-variete="{job.get('variete', '')}"
                 data-quantite="{int(job.get('quantite_pallox') or 0)}"
                 data-poids="{float(job.get('poids_brut_kg') or 0)}"
                 data-duree="{duree_minutes}"
                 data-statut-source="{job.get('statut_source') or ''}"
                 data-producteur="{job.get('producteur') or ''}"
                 style="cursor: move; margin: 8px 0; padding: 10px; background: #2e7d32; color: white; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <div style="font-weight: 600; margin-bottom: 4px;">
                    {job.get('code_lot_interne', 'Job')}
                </div>
                <div style="font-size: 0.85em; opacity: 0.9;">
                    🌱 {job.get('variete', '-') } | 📦 {int(job.get('quantite_pallox') or 0)}P | ⚖️ {poids_tonnes:.1f}T
                </div>
                <div style="font-size: 0.8em; opacity: 0.8; margin-top: 4px;">
                    ⏱️ {duree_minutes // 60}h{duree_minutes % 60:02d}min
                </div>
            </div>
            """

        draggable_html += """
        </div>

        <script src='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.10/index.global.min.js'></script>
        <script src='https://cdn.jsdelivr.net/npm/@fullcalendar/interaction@6.1.10/index.global.min.js'></script>
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                var containerEl = document.getElementById('external-events');

                if (!containerEl) {
                    return;
                }

                new FullCalendar.Draggable(containerEl, {
                    itemSelector: '.fc-event',
                    eventData: function(eventEl) {
                        return {
                            title: eventEl.getAttribute('data-code-lot'),
                            duration: eventEl.getAttribute('data-duration'),
                            backgroundColor: '#2e7d32',
                            borderColor: '#1b5e20',
                            extendedProps: {
                                job_id: parseInt(eventEl.getAttribute('data-job-id')),
                                code_lot_interne: eventEl.getAttribute('data-code-lot'),
                                variete: eventEl.getAttribute('data-variete'),
                                quantite_pallox: parseInt(eventEl.getAttribute('data-quantite')),
                                poids_brut_kg: parseFloat(eventEl.getAttribute('data-poids')),
                                duree_minutes: parseInt(eventEl.getAttribute('data-duree')),
                                statut_source: eventEl.getAttribute('data-statut-source'),
                                producteur: eventEl.getAttribute('data-producteur')
                            }
                        };
                    }
                });
            });
        </script>
        """

        components.html(draggable_html, height=500, scrolling=True)

with col_calendar:
    st.subheader("📅 Calendrier Lavage")
    calendar_event = fullcalendar_component(
        events=build_calendar_events(planning_df),
        editable=True,
        droppable=True,
        height=650,
        initial_date=str(week_start),
        key=f"calendar_lavage_bis_{selected_line}"
    )

    if calendar_event:
        event_type = calendar_event.get("type")

        if event_type == "external_drop":
            job_id = calendar_event.get("job_id")
            start_dt = parse_iso_datetime(calendar_event.get("start"))
            end_dt = parse_iso_datetime(calendar_event.get("end"))
            duree_minutes = calendar_event.get("duree_minutes")

            if not end_dt and start_dt:
                end_dt = start_dt + timedelta(minutes=int(duree_minutes or 60))

            if job_id and start_dt and end_dt:
                ok, msg = insert_planning_element(
                    job_id=job_id,
                    ligne_lavage=selected_line,
                    start_dt=start_dt,
                    end_dt=end_dt,
                    duree_minutes=int(duree_minutes or (end_dt - start_dt).total_seconds() / 60)
                )
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

        if event_type in {"drop", "resize"}:
            planning_element_id = calendar_event.get("job_id")
            start_dt = parse_iso_datetime(calendar_event.get("new_start"))
            end_dt = parse_iso_datetime(calendar_event.get("new_end"))
            if planning_element_id and start_dt and end_dt:
                ok, msg = update_planning_element(planning_element_id, start_dt, end_dt)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
