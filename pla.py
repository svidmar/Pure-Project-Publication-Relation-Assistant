import streamlit as st
import pandas as pd
import requests
from urllib.parse import urlparse
import uuid as uuidlib
import io

st.set_page_config(page_title="Pure Project-Publication Relation Assistant", layout="wide")
st.title("Pure Project-Publication Relation Assistant")

st.markdown("""
### 🔗 **Pure Project-Publication Relation Assistant**

This tool helps identify and semi-automatically **bulk relate publications to projects** in Elsevier's Pure using **project identifiers** and **DOIs**. It supports a wide range of identifier types, such as *External Project ID*, *Contract ID*, and *Horizon ID* — based on the configured identifier types in Pure.

#### 🔍 **What it does**
- Looks up the project using the provided **ProjectID** (or just the Pure Project UUID) — and now also supports **GrantID**.
- Searches for the publication in Pure based on the DOI.
- Flags existing relations and determines which are ready to be related.
- Shows matched identifier type and flags ambiguous project matches.
- Supports `dry run` mode for safe pre-inspection of results.
- Can be used to identify **potentially missing research projects** in Pure.
- Useful when you have a list of Project or Grant IDs and related DOIs from systems like **OpenAlex**, **CORDIS**, or similar, to bulk-set these relations in Pure.

---

### ✅ **Recommended Workflow**
1. Input Pure **Base URL**
2. Input valid **Pure API Key** with appropriate permissions
3. **Upload a CSV** with at least two columns: `ProjectID` **or** `GrantID`, and `DOI` (supports both `,` and `;` separators).
4. **Run the tool once** in **dry run mode**:
   - Review the matching results.
   - Download the resulting table.
   - **Filter out rows** where no linking is needed or where there are ambiguous matches.
5. **Re-upload the cleaned file** (with only "ready to link" rows - it speeds up the writeback).
6. Disable dry run and click **"Confirm and Link in Pure"** to write the new relations to Pure.

Use at your own risk 😉

---
""")

# --- API Setup ---
base_url = st.text_input("PURE Base URL (e.g. https://vbn.aau.dk)", value="https://vbn.aau.dk")
api_key = st.text_input("PURE API Key", type="password")

safe_api_key = api_key.encode("ascii", "ignore").decode("ascii")

headers = {
    "Accept": "application/json",
    "api-key": safe_api_key,
    "Content-Type": "application/json"
}

# --- Get allowed identifier types ---
idtype_url = f"{base_url}/ws/api/projects/allowed-classified-identifier-types"
idtype_resp = requests.get(idtype_url, headers=headers)
idtype_map = {}  # {uri: label}
if idtype_resp.ok:
    for item in idtype_resp.json().get("classifications", []):
        uri = item.get("uri")
        label = item.get("term", {}).get("en_GB", uri)
        idtype_map[uri] = label

uploaded_file = st.file_uploader("Upload CSV with ProjectID or GrantID, and DOI", type="csv")
dry_run = st.checkbox("Dry run mode", value=True)

if uploaded_file:
    content = uploaded_file.read().decode("utf-8")
    sep = "," if content.count(",") >= content.count(";") else ";"

    # Load all columns as string to preserve leading zeroes
    df = pd.read_csv(io.StringIO(content), sep=sep, dtype=str)

    # Normalize column names
    df.columns = [col.strip().lower() for col in df.columns]

    if st.button("Start Matching"):
        # Prepare result columns
        df["project_uuid"] = None
        df["publication_uuid"] = None
        df["project_title"] = None
        df["publication_title"] = None
        df["status"] = None
        df["link"] = False
        df["matched_identifier_type_uri"] = None
        df["matched_identifier_label"] = None
        df["identifier_warning"] = None
        df["input_id_source"] = None  # New: which column was used (ProjectID or GrantID)

        st.info("Looking up projects and publications in Pure...")

        for idx, row in df.iterrows():
            # Accept ProjectID or GrantID (prefer ProjectID if both present)
            pid = str(row.get("projectid", "") or "").strip()
            gid = str(row.get("grantid", "") or "").strip()
            project_id_value = pid if pid else gid
            input_source = "ProjectID" if pid else ("GrantID" if gid else None)
            df.at[idx, "input_id_source"] = input_source

            # Validate presence of an ID
            if not project_id_value:
                df.at[idx, "status"] = "No ProjectID or GrantID provided"
                continue

            # DOI normalization
            raw_doi = str(row.get("doi", "")).strip()
            if raw_doi.startswith("http"):
                parsed = urlparse(raw_doi)
                doi = parsed.path.lstrip("/")
            else:
                doi = raw_doi

            project_uuid = None
            found_project = None
            match_count = 0

            # If the ID provided is a UUID, try direct fetch
            try:
                uuidlib.UUID(project_id_value, version=4)
                project_uuid = project_id_value
                pj = requests.get(f"{base_url}/ws/api/projects/{project_uuid}", headers=headers)
                if pj.ok:
                    found_project = pj.json()
            except ValueError:
                pass

            # Otherwise, search in identifiers
            if not found_project:
                search_payload = {"searchString": project_id_value}
                proj_resp = requests.post(f"{base_url}/ws/api/projects/search", headers=headers, json=search_payload)
                if proj_resp.ok:
                    for item in proj_resp.json().get("items", []):
                        for identifier in item.get("identifiers", []):
                            if str(identifier.get("id", "")).strip() == project_id_value:
                                match_count += 1
                                if not found_project:
                                    project_uuid = item.get("uuid")
                                    found_project = item
                                    id_type_uri = identifier.get("type", {}).get("uri")
                                    df.at[idx, "matched_identifier_type_uri"] = id_type_uri
                                    df.at[idx, "matched_identifier_label"] = idtype_map.get(id_type_uri, id_type_uri)
                    if match_count > 1:
                        df.at[idx, "identifier_warning"] = f"⚠ Multiple matches for {input_source}"

            if not found_project:
                df.at[idx, "status"] = "Project not found"
                continue

            df.at[idx, "project_uuid"] = project_uuid
            df.at[idx, "project_title"] = found_project.get("title", {}).get("en_GB", "") or found_project.get("title", {}).get("value", "")

            # Find publication by DOI
            try:
                pub_resp = requests.post(
                    f"{base_url}/ws/api/research-outputs/search",
                    headers=headers,
                    json={"searchString": doi}
                )
                pub_json = pub_resp.json()
            except Exception as e:
                df.at[idx, "status"] = f"DOI lookup failed: {e}"
                continue

            found_pub = None

            if pub_resp.ok and pub_json.get("count", 0) > 0:
                for item in pub_json.get("items", []):
                    for ev in item.get("electronicVersions", []):
                        if ev.get("typeDiscriminator") == "DoiElectronicVersion" and ev.get("doi", "").strip().lower() == doi.lower():
                            found_pub = item
                            break
                    if found_pub:
                        break

            if not found_pub:
                df.at[idx, "status"] = "DOI not found in Pure"
                continue

            pub_uuid = found_pub["uuid"]
            df.at[idx, "publication_uuid"] = pub_uuid
            df.at[idx, "publication_title"] = found_pub.get("title", {}).get("value", "")

            # Check existing relations to avoid overwriting/removing
            full_proj = requests.get(f"{base_url}/ws/api/projects/{project_uuid}", headers=headers).json()
            existing_outputs = [
                ro["researchOutput"]["uuid"]
                for ro in full_proj.get("researchOutputs", [])
                if "researchOutput" in ro and "uuid" in ro["researchOutput"]
            ]

            if pub_uuid in existing_outputs:
                df.at[idx, "status"] = "Already linked"
            else:
                df.at[idx, "status"] = "Ready to link"
                df.at[idx, "link"] = True

        st.session_state["matched_df"] = df

if "matched_df" in st.session_state:
    df = st.session_state["matched_df"]
    st.subheader("Project-Publication relations")
    sorted_df = df.sort_values(by="link", ascending=False)
    st.dataframe(sorted_df, use_container_width=True)

    to_link_df = df[df["link"] & (df["status"] == "Ready to link") & (df["identifier_warning"].isna())]

    if not to_link_df.empty:
        st.subheader("Summary of Pending Changes")
        st.dataframe(to_link_df[["project_title", "publication_title", "matched_identifier_label", "input_id_source"]], use_container_width=True)

        if st.button("Confirm and Link in Pure"):
            with st.spinner("Writing links to Pure..."):
                success = 0
                fail = 0
                log = []
                grouped = to_link_df.groupby("project_uuid")

                for proj_uuid, group in grouped:
                    to_add = group["publication_uuid"].tolist()

                    current = requests.get(f"{base_url}/ws/api/projects/{proj_uuid}", headers=headers).json()
                    existing = [
                        ro["researchOutput"]["uuid"]
                        for ro in current.get("researchOutputs", [])
                        if "researchOutput" in ro and "uuid" in ro["researchOutput"]
                    ]
                    all_uuids = list(set(existing + to_add))

                    payload = {
                        "researchOutputs": [
                            {"researchOutput": {"systemName": "ResearchOutput", "uuid": u}}
                            for u in all_uuids
                        ]
                    }

                    if dry_run:
                        for puid in to_add:
                            log.append((proj_uuid, puid, "✅ Dry run"))
                    else:
                        put_resp = requests.put(
                            f"{base_url}/ws/api/projects/{proj_uuid}",
                            headers=headers,
                            json=payload
                        )

                        if put_resp.ok:
                            success += len(to_add)
                            for puid in to_add:
                                log.append((proj_uuid, puid, "✅ Linked"))
                        else:
                            fail += len(to_add)
                            for puid in to_add:
                                log.append((proj_uuid, puid, f"❌ Failed ({put_resp.status_code})"))

            if dry_run:
                st.success("Dry run completed. No changes were made.")
            else:
                st.success(f"Linked {success} publications. {fail} failed.")

            st.subheader("Linking Log")
            log_df = pd.DataFrame(log, columns=["Project UUID", "Publication UUID", "Result"])
            st.dataframe(log_df, use_container_width=True)
    else:
        st.info("No valid link candidates to process.")

st.markdown(
    """
    <div style='font-size: 0.9em; margin-top: 2em;'>
        <strong>Created by:</strong><br>
        Søren Vidmar<br>
        🔗 <a href='https://orcid.org/0000-0003-3055-6053'>ORCID</a><br>
        🏫 Aalborg University<br>
        📧 <a href='mailto:sv@aub.aau.dk'>sv@aub.aau.dk</a><br>
        📦 <a href='https://github.com/svidmar'>GitHub</a>
    </div>
    """,
    unsafe_allow_html=True
)