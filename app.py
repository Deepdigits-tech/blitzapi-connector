"""BlitzAPI Connector — General-purpose Streamlit app for all BlitzAPI endpoints."""

import io
import streamlit as st
import pandas as pd
from blitz_client import BlitzClient

# ── Page Config ──────────────────────────────────────────────
st.set_page_config(page_title="BlitzAPI Connector", page_icon="⚡", layout="wide")

# ── API Key ──────────────────────────────────────────────────
api_key = st.secrets.get("BLITZ_API_KEY", "")
if not api_key or api_key == "your-api-key-here":
    st.error("Set your BlitzAPI key in `.streamlit/secrets.toml` (local) or Streamlit Cloud Secrets.")
    st.stop()

client = BlitzClient(api_key)

# ── Sidebar: Credit Tracker ──────────────────────────────────
with st.sidebar:
    st.title("⚡ BlitzAPI Connector")
    st.caption("General-purpose lead search & enrichment")
    st.divider()
    if st.button("🔄 Refresh Credits"):
        st.session_state.pop("credits_info", None)
    try:
        if "credits_info" not in st.session_state:
            st.session_state.credits_info = client.get_key_info()
        info = st.session_state.credits_info
        st.metric("Credits Remaining", info.get("remaining_credits", "N/A"))
        plans = info.get("active_plans", [])
        plan_name = plans[0].get("name", "N/A") if plans else "Free"
        st.caption(f"Plan: {plan_name}")
    except Exception as e:
        st.warning(f"Could not fetch credit info: {e}")


# ── Helpers ──────────────────────────────────────────────────
def to_dataframe(data) -> pd.DataFrame:
    """Convert API response to DataFrame, handling nested structures."""
    if isinstance(data, list):
        return pd.json_normalize(data)
    if isinstance(data, dict):
        for key in ("results", "data", "employees", "companies", "people", "all_emails"):
            if key in data and isinstance(data[key], list):
                return pd.json_normalize(data[key])
        return pd.json_normalize([data])
    return pd.DataFrame()


def show_results(data, label: str = "results"):
    """Display results as a table with CSV download."""
    df = to_dataframe(data)
    if df.empty:
        st.info("No results found.")
        return
    st.success(f"Found {len(df)} {label}")
    st.dataframe(df, use_container_width=True)
    csv = df.to_csv(index=False)
    st.download_button(
        f"⬇️ Download {label} as CSV",
        csv,
        file_name=f"blitzapi_{label}.csv",
        mime="text/csv",
    )


def handle_error(e: Exception):
    """Display friendly error messages."""
    msg = str(e)
    if "401" in msg or "403" in msg:
        st.error("Authentication failed. Check your API key.")
    elif "429" in msg:
        st.warning("Rate limit hit. Wait a moment and try again.")
    elif "402" in msg:
        st.error("Insufficient credits. Top up your BlitzAPI account.")
    else:
        st.error(f"API error: {msg}")


def bulk_process(uploaded_file, url_column: str, process_fn, label: str):
    """Process a CSV of LinkedIn URLs through a given function."""
    df = pd.read_csv(uploaded_file)
    if url_column not in df.columns:
        st.error(f"CSV must have a `{url_column}` column.")
        return
    urls = df[url_column].dropna().tolist()
    st.info(f"Processing {len(urls)} URLs...")
    progress = st.progress(0)
    results = []
    for i, url in enumerate(urls):
        try:
            result = process_fn(url.strip())
            result["input_url"] = url
            results.append(result)
        except Exception as e:
            results.append({"input_url": url, "error": str(e)})
        progress.progress((i + 1) / len(urls))
    show_results(results, label)


def parse_comma_list(text: str) -> list[str]:
    """Split comma-separated input into a list, stripping whitespace."""
    return [x.strip() for x in text.split(",") if x.strip()] if text else []


# ── Tabs ─────────────────────────────────────────────────────
tabs = st.tabs([
    "🔍 Find Companies",
    "👥 Find Employees",
    "🎯 Waterfall ICP",
    "📧 Find Email",
    "📱 Find Phone",
    "🏢 Company Enrichment",
    "🔄 Reverse Lookup",
    "🔗 Domain ↔ LinkedIn",
])

# ── Tab 1: Find Companies ────────────────────────────────────
with tabs[0]:
    st.header("Find Companies")
    st.caption("Search by keywords, industry, location, and employee count")

    col1, col2 = st.columns(2)
    with col1:
        fc_keywords = st.text_input("Keywords (comma-separated)", placeholder="e.g. SaaS, AI, education", key="fc_kw")
        fc_industry = st.text_input("Industry (comma-separated)", placeholder="e.g. Software Development, Education", key="fc_ind")
        fc_limit = st.slider("Max results", 5, 50, 25, key="fc_limit")
    with col2:
        fc_country = st.text_input("Country codes (comma-separated)", placeholder="e.g. US, CA, GB", key="fc_country")
        fc_city = st.text_input("City (comma-separated)", placeholder="e.g. San Francisco, New York", key="fc_city")
        fc_emp_range = st.multiselect(
            "Employee range",
            ["1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000", "5001-10000", "10001+"],
            key="fc_emp_range",
        )

    if st.button("🔍 Search Companies", type="primary", key="fc_btn"):
        with st.spinner("Searching..."):
            try:
                data = client.find_companies(
                    keywords_include=parse_comma_list(fc_keywords) or None,
                    industry_include=parse_comma_list(fc_industry) or None,
                    country_codes=parse_comma_list(fc_country) or None,
                    city_include=parse_comma_list(fc_city) or None,
                    employee_range=fc_emp_range or None,
                    max_results=fc_limit,
                )
                show_results(data, "companies")
            except Exception as e:
                handle_error(e)

# ── Tab 2: Find Employees ────────────────────────────────────
with tabs[1]:
    st.header("Find Employees")
    st.caption("Find contacts at a target company (requires company LinkedIn URL)")

    fe_linkedin = st.text_input("Company LinkedIn URL", placeholder="https://linkedin.com/company/stripe", key="fe_li")

    col1, col2 = st.columns(2)
    with col1:
        fe_level = st.multiselect(
            "Job level",
            ["Owner", "Partner", "CXO", "VP", "Director", "Manager", "Senior", "Entry", "Training", "Unpaid"],
            key="fe_level",
        )
    with col2:
        fe_function = st.multiselect(
            "Job function",
            ["Accounting", "Administrative", "Arts and Design", "Business Development",
             "Community and Social Services", "Consulting", "Education", "Engineering",
             "Entrepreneurship", "Finance", "Healthcare Services", "Human Resources",
             "Information Technology", "Legal", "Marketing", "Media and Communication",
             "Military and Protective Services", "Operations", "Product Management",
             "Program and Project Management", "Purchasing", "Quality Assurance",
             "Real Estate", "Research", "Sales", "Support"],
            key="fe_function",
        )
    fe_limit = st.slider("Max results", 5, 50, 25, key="fe_limit")

    if st.button("👥 Find Employees", type="primary", key="fe_btn"):
        if not fe_linkedin:
            st.warning("Enter a company LinkedIn URL.")
        else:
            with st.spinner("Searching..."):
                try:
                    data = client.find_employees(
                        company_linkedin_url=fe_linkedin,
                        job_level=fe_level or None,
                        job_function=fe_function or None,
                        max_results=fe_limit,
                    )
                    show_results(data, "employees")
                except Exception as e:
                    handle_error(e)

# ── Tab 3: Waterfall ICP Search ──────────────────────────────
with tabs[2]:
    st.header("Waterfall ICP Search")
    st.caption("Find the best-match decision-maker using a title cascade (tries each level until a match is found)")

    wf_linkedin = st.text_input("Company LinkedIn URL", placeholder="https://linkedin.com/company/hubspot", key="wf_li")

    st.subheader("Title Cascade")
    st.caption("Each row is a priority level. The search tries level 1 first, then falls back to level 2, etc.")

    num_levels = st.number_input("Number of cascade levels", min_value=1, max_value=5, value=2, key="wf_levels")
    cascade = []
    for i in range(int(num_levels)):
        with st.expander(f"Level {i + 1}", expanded=(i == 0)):
            titles = st.text_input(f"Include titles (comma-separated)", placeholder="e.g. CMO, VP Marketing", key=f"wf_inc_{i}")
            exclude = st.text_input(f"Exclude titles (comma-separated)", placeholder="e.g. Intern, Assistant", key=f"wf_exc_{i}")
            level_data = {
                "include_title": parse_comma_list(titles),
                "location": [],
                "include_headline_search": True,
            }
            if exclude:
                level_data["exclude_title"] = parse_comma_list(exclude)
            if level_data["include_title"]:
                cascade.append(level_data)

    wf_max = st.slider("Max results", 1, 10, 5, key="wf_max")

    if st.button("🎯 Search ICP", type="primary", key="wf_btn"):
        if not wf_linkedin:
            st.warning("Enter a company LinkedIn URL.")
        elif not cascade:
            st.warning("Add at least one title in the cascade.")
        else:
            with st.spinner("Running waterfall search..."):
                try:
                    data = client.waterfall_icp_search(
                        company_linkedin_url=wf_linkedin,
                        cascade=cascade,
                        max_results=wf_max,
                    )
                    show_results(data, "ICP matches")
                except Exception as e:
                    handle_error(e)

# ── Tab 4: Find Work Email ───────────────────────────────────
with tabs[3]:
    st.header("Find Work Email")
    st.caption("Get SMTP-validated work email from LinkedIn profile URL")

    mode = st.radio("Mode", ["Single lookup", "Bulk (CSV upload)"], key="email_mode", horizontal=True)

    if mode == "Single lookup":
        em_url = st.text_input("LinkedIn profile URL", placeholder="https://linkedin.com/in/johndoe", key="em_url")
        if st.button("📧 Find Email", type="primary", key="em_btn"):
            if not em_url:
                st.warning("Enter a LinkedIn URL.")
            else:
                with st.spinner("Looking up email..."):
                    try:
                        data = client.find_work_email(em_url)
                        show_results(data, "email results")
                    except Exception as e:
                        handle_error(e)
    else:
        st.info("Upload a CSV with a `linkedin_url` column.")
        uploaded = st.file_uploader("Upload CSV", type=["csv"], key="em_csv")
        if uploaded and st.button("📧 Process Bulk Emails", type="primary", key="em_bulk_btn"):
            bulk_process(uploaded, "linkedin_url", client.find_work_email, "email results")

# ── Tab 5: Find Phone ────────────────────────────────────────
with tabs[4]:
    st.header("Find Phone")
    st.caption("Get mobile/direct phone from LinkedIn profile URL (Mega plan required)")

    mode = st.radio("Mode", ["Single lookup", "Bulk (CSV upload)"], key="phone_mode", horizontal=True)

    if mode == "Single lookup":
        ph_url = st.text_input("LinkedIn profile URL", placeholder="https://linkedin.com/in/johndoe", key="ph_url")
        if st.button("📱 Find Phone", type="primary", key="ph_btn"):
            if not ph_url:
                st.warning("Enter a LinkedIn URL.")
            else:
                with st.spinner("Looking up phone..."):
                    try:
                        data = client.find_phone(ph_url)
                        show_results(data, "phone results")
                    except Exception as e:
                        handle_error(e)
    else:
        st.info("Upload a CSV with a `linkedin_url` column.")
        uploaded = st.file_uploader("Upload CSV", type=["csv"], key="ph_csv")
        if uploaded and st.button("📱 Process Bulk Phones", type="primary", key="ph_bulk_btn"):
            bulk_process(uploaded, "linkedin_url", client.find_phone, "phone results")

# ── Tab 6: Company Enrichment ────────────────────────────────
with tabs[5]:
    st.header("Company Enrichment")
    st.caption("Get full company profile from LinkedIn URL or domain (via domain→LinkedIn first)")

    ce_input_type = st.radio("Input type", ["LinkedIn URL", "Domain"], key="ce_type", horizontal=True)

    if ce_input_type == "LinkedIn URL":
        ce_linkedin = st.text_input("LinkedIn company URL", placeholder="https://linkedin.com/company/stripe", key="ce_li")
        if st.button("🏢 Enrich Company", type="primary", key="ce_btn"):
            if not ce_linkedin:
                st.warning("Enter a LinkedIn URL.")
            else:
                with st.spinner("Enriching..."):
                    try:
                        data = client.enrich_company(linkedin_url=ce_linkedin)
                        show_results(data, "company data")
                    except Exception as e:
                        handle_error(e)
    else:
        ce_domain = st.text_input("Domain", placeholder="e.g. stripe.com", key="ce_domain")
        if st.button("🏢 Enrich Company", type="primary", key="ce_domain_btn"):
            if not ce_domain:
                st.warning("Enter a domain.")
            else:
                with st.spinner("Resolving domain → LinkedIn, then enriching..."):
                    try:
                        resolved = client.domain_to_linkedin(ce_domain)
                        li_url = resolved.get("company_linkedin_url", "")
                        if not li_url:
                            st.warning("Could not resolve domain to a LinkedIn URL.")
                        else:
                            data = client.enrich_company(linkedin_url=li_url)
                            show_results(data, "company data")
                    except Exception as e:
                        handle_error(e)

# ── Tab 7: Reverse Lookup ────────────────────────────────────
with tabs[6]:
    st.header("Reverse Lookup")
    st.caption("Find person details from an email or phone number")

    lookup_type = st.radio("Lookup by", ["Email", "Phone"], key="rl_type", horizontal=True)

    if lookup_type == "Email":
        rl_email = st.text_input("Email address", placeholder="john@stripe.com", key="rl_email")
        if st.button("🔄 Reverse Lookup", type="primary", key="rl_email_btn"):
            if not rl_email:
                st.warning("Enter an email address.")
            else:
                with st.spinner("Looking up..."):
                    try:
                        data = client.reverse_email_lookup(rl_email)
                        show_results(data, "person data")
                    except Exception as e:
                        handle_error(e)
    else:
        rl_phone = st.text_input("Phone number", placeholder="+14155551234", key="rl_phone")
        if st.button("🔄 Reverse Lookup", type="primary", key="rl_phone_btn"):
            if not rl_phone:
                st.warning("Enter a phone number.")
            else:
                with st.spinner("Looking up..."):
                    try:
                        data = client.reverse_phone_lookup(rl_phone)
                        show_results(data, "person data")
                    except Exception as e:
                        handle_error(e)

# ── Tab 8: Domain ↔ LinkedIn ─────────────────────────────────
with tabs[7]:
    st.header("Domain ↔ LinkedIn Converter")

    direction = st.radio("Convert", ["Domain → LinkedIn URL", "LinkedIn URL → Domain"], key="dl_dir", horizontal=True)

    if direction == "Domain → LinkedIn URL":
        dl_domain = st.text_input("Domain", placeholder="e.g. stripe.com", key="dl_domain")
        if st.button("🔗 Convert", type="primary", key="dl_d2l_btn"):
            if not dl_domain:
                st.warning("Enter a domain.")
            else:
                with st.spinner("Converting..."):
                    try:
                        data = client.domain_to_linkedin(dl_domain)
                        show_results(data, "LinkedIn URL")
                    except Exception as e:
                        handle_error(e)
    else:
        dl_linkedin = st.text_input("LinkedIn company URL", placeholder="https://linkedin.com/company/stripe", key="dl_linkedin")
        if st.button("🔗 Convert", type="primary", key="dl_l2d_btn"):
            if not dl_linkedin:
                st.warning("Enter a LinkedIn URL.")
            else:
                with st.spinner("Converting..."):
                    try:
                        data = client.linkedin_to_domain(dl_linkedin)
                        show_results(data, "domain")
                    except Exception as e:
                        handle_error(e)
