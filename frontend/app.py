import streamlit as st
import requests
import pandas as pd

import os
from dotenv import load_dotenv
load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000") # replace after deploy

st.set_page_config(
    page_title="Fact-Check Agent",
    page_icon="🔍",
    layout="wide"
)

# ── Styling ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.verified   { background:#d1fae5; color:#065f46; padding:4px 10px; border-radius:12px; font-weight:600; font-size:13px; }
.inaccurate { background:#fef3c7; color:#92400e; padding:4px 10px; border-radius:12px; font-weight:600; font-size:13px; }
.false      { background:#fee2e2; color:#991b1b; padding:4px 10px; border-radius:12px; font-weight:600; font-size:13px; }
.unverifiable { background:#e5e7eb; color:#374151; padding:4px 10px; border-radius:12px; font-weight:600; font-size:13px; }
.metric-box { text-align:center; padding:16px; border-radius:10px; margin:4px; }
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────────────────────
st.title("🔍 Fact-Check Agent")
st.caption("Upload a PDF — the agent extracts claims, searches the web, and verdicts each one.")

st.divider()

# ── Upload ───────────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader("Upload a PDF document", type=["pdf"])

if uploaded_file:
    st.info(f"📄 **{uploaded_file.name}** — {round(uploaded_file.size / 1024, 1)} KB")

    if st.button("🚀 Run Fact-Check", type="primary"):
        with st.spinner("Extracting claims and verifying against live web data..."):
            try:
                response = requests.post(
                    f"{BACKEND_URL}/analyze",
                    files={"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")},
                    timeout=300,  # large PDFs can take time
                )

                if response.status_code == 200:
                    report = response.json()
                    st.success("Analysis complete!")

                    # ── Summary metrics ───────────────────────────────────
                    st.subheader("Summary")
                    c1, c2, c3, c4, c5 = st.columns(5)
                    c1.metric("Total Claims", report["total_claims"])
                    c2.metric("✅ Verified",      report["verified_count"])
                    c3.metric("⚠️ Inaccurate",   report["inaccurate_count"])
                    c4.metric("❌ False",          report["false_count"])
                    c5.metric("❓ Unverifiable",  report["unverifiable_count"])

                    st.divider()

                    # ── Filters ───────────────────────────────────────────
                    st.subheader("Claims")
                    verdict_filter = st.multiselect(
                        "Filter by verdict",
                        ["VERIFIED", "INACCURATE", "FALSE", "UNVERIFIABLE"],
                        default=["VERIFIED", "INACCURATE", "FALSE", "UNVERIFIABLE"]
                    )

                    filtered = [c for c in report["claims"] if c["verdict"] in verdict_filter]

                    # ── Claim cards ───────────────────────────────────────
                    for claim in filtered:
                        verdict = claim["verdict"]
                        badge_class = verdict.lower()

                        with st.expander(f'#{claim["id"]} — {claim["text"][:80]}{"..." if len(claim["text"]) > 80 else ""}'):
                            col1, col2 = st.columns([1, 3])

                            with col1:
                                st.markdown(f'<span class="{badge_class}">{verdict}</span>', unsafe_allow_html=True)
                                st.caption(f"Category: {claim['category']}")

                            with col2:
                                st.markdown(f"**Claim:** {claim['text']}")
                                st.markdown(f"**Reason:** {claim['reason']}")

                                if claim.get("correct_value"):
                                    st.markdown(f"**Correct value:** `{claim['correct_value']}`")

                                if claim.get("sources"):
                                    st.markdown("**Sources:**")
                                    for url in claim["sources"]:
                                        st.markdown(f"- {url}")

                    # ── Download report ───────────────────────────────────
                    st.divider()
                    df = pd.DataFrame([{
                        "ID": c["id"],
                        "Claim": c["text"],
                        "Category": c["category"],
                        "Verdict": c["verdict"],
                        "Reason": c["reason"],
                        "Correct Value": c.get("correct_value", ""),
                    } for c in report["claims"]])

                    st.download_button(
                        label="📥 Download report as CSV",
                        data=df.to_csv(index=False),
                        file_name=f"factcheck_{uploaded_file.name.replace('.pdf','')}.csv",
                        mime="text/csv",
                    )

                else:
                    detail = response.json().get("detail", "Unknown error")
                    st.error(f"Backend error: {detail}")

            except requests.exceptions.ConnectionError:
                st.error("Cannot reach backend. Make sure it's running and BACKEND_URL is set correctly.")
            except requests.exceptions.Timeout:
                st.error("Request timed out. The PDF may be too large or the backend is overloaded.")
            except Exception as e:
                st.error(f"Unexpected error: {e}")