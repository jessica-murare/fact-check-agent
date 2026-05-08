import streamlit as st
import requests
import pandas as pd

import os
from dotenv import load_dotenv
load_dotenv()


def get_backend_url() -> str:
    try:
        return st.secrets.get("BACKEND_URL", os.getenv("BACKEND_URL", "http://localhost:8000"))
    except Exception:
        return os.getenv("BACKEND_URL", "http://localhost:8000")


BACKEND_URL = get_backend_url() # replace after deploy


def get_error_detail(response: requests.Response) -> str:
    try:
        data = response.json()
        return data.get("detail", data)
    except ValueError:
        return response.text or f"HTTP {response.status_code}"

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

                    # ── Overall confidence ───────────────────────────────
                    avg_confidence = round(
                        sum(c.get("confidence", 50) for c in report["claims"]) / len(report["claims"])
                    )

                    if avg_confidence >= 70:
                        conf_color = "#10b981"
                    elif avg_confidence >= 40:
                        conf_color = "#f59e0b"
                    else:
                        conf_color = "#ef4444"

                    st.markdown(f"""
                    <div style="background:#f9fafb; border:1px solid #e5e7eb; border-radius:10px; padding:16px; text-align:center">
                        <div style="font-size:14px; color:#6b7280">Overall Report Confidence</div>
                        <div style="font-size:36px; font-weight:700; color:{conf_color}">{avg_confidence}%</div>
                        <div style="background:#e5e7eb; border-radius:6px; height:10px; margin-top:8px">
                            <div style="background:{conf_color}; width:{avg_confidence}%; height:10px; border-radius:6px"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

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

                                # ── Confidence bar ────────────────────────
                                confidence = claim.get("confidence", 50)

                                if confidence >= 70:
                                    bar_color = "#10b981"
                                elif confidence >= 40:
                                    bar_color = "#f59e0b"
                                else:
                                    bar_color = "#ef4444"

                                st.markdown(f"""
                                <div style="margin-top:10px">
                                    <div style="font-size:12px; color:#6b7280; margin-bottom:4px">
                                        Confidence: <b>{confidence}%</b>
                                    </div>
                                    <div style="background:#e5e7eb; border-radius:6px; height:8px; width:100%">
                                        <div style="background:{bar_color}; width:{confidence}%;
                                                    height:8px; border-radius:6px; transition:width 0.3s">
                                        </div>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

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
                        "Confidence": f"{c.get('confidence', 50)}%",
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
                    detail = get_error_detail(response)
                    st.error(f"Backend error: {detail}")

            except requests.exceptions.ConnectionError:
                st.error("Cannot reach backend. Make sure it's running and BACKEND_URL is set correctly.")
            except requests.exceptions.Timeout:
                st.error("Request timed out. The PDF may be too large or the backend is overloaded.")
            except Exception as e:
                st.error(f"Unexpected error: {e}")
