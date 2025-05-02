
# Pure Project-Publication Relation Assistant

This Streamlit app helps identify and semi-automatically **bulk relate publications to projects** in Elsevier's Pure using **project identifiers** and **DOIs**.  
It supports a wide range of identifier types, such as _External Project ID_, _Contract ID_, and _Horizon ID_ — based on your local Pure configuration.

## 🔍 What It Does

- Looks up the project using the provided ProjectID (or just the Pure Project UUID).
- Searches for the publication in Pure based on the DOI.
- Validates matches to ensure accuracy and prevent incorrect links.
- Flags existing relations and determines which are ready to be linked.
- Displays the matched identifier type and warns about ambiguous project matches.
- Includes a `dry run` mode for safe pre-inspection of potential changes.

## 🌍 External Data Integration

This tool is especially useful if you have a list of projects and related publications from systems like **OpenAlex**, **CORDIS**, or other external sources.  
With this assistant, you can semi-automatically set these relations inside Pure, if the identifiers and DOIs are available.

## ✅ Recommended Workflow

1. **Upload a CSV** with two columns: `ProjectID` and `DOI`  
   (Both comma `,` and semicolon `;` separators are supported.)
2. **Run the tool in `Dry run` mode** to preview matches and issues.
3. **Filter the result** to remove ambiguous or unmatched rows.
4. **Re-upload the cleaned file** and run again with `Dry run` disabled to apply the changes.

## 🛠️ Features

- Skips over ambiguous matches (or warns about them).
- Ensures no existing publication links are overwritten — it appends only.
- Option to download the result and edit outside Streamlit.
- Logs all changes made during writeback.

## 📋 Example CSV Format

```csv
ProjectID,DOI
101137074,10.1080/17459737.2017.1406012
H2020-ICT-2018-2,10.1016/j.patter.2020.100150
```

## 👤 Author

**Created by:**  
Søren Vidmar  
🔗 [ORCID](https://orcid.org/0000-0003-3055-6053)  
🏫 Aalborg University  
📧 [sv@aub.aau.dk](mailto:sv@aub.aau.dk)  
📦 [GitHub](https://github.com/svidmar)

---

This tool is designed to help reduce manual work and improve the data quality and completeness of research project-publication relations in Pure.
