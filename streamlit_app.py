# streamlit_app.py
import streamlit as st
import requests
import os

API_BASE = st.secrets.get("API_BASE", "http://localhost:8000")

st.title("Outlook Web Automation — Test UI")

# --- Job submission ---
st.header("Submit job (single CURP)")
curp = st.text_input("CURP")
if st.button("Submit job"):
    if not curp:
        st.error("Enter CURP")
    else:
        r = requests.post(f"{API_BASE}/jobs", json={"curp": curp})  # ✅ fixed key
        if r.ok:
            job = r.json()
            st.success("Job submitted successfully")
            st.json(job)
        else:
            st.error(r.text)

# --- Job status ---
st.header("Check job status")
job_id = st.text_input("Job ID to check")
if st.button("Get job"):
    if not job_id:
        st.error("Enter job id")
    else:
        r = requests.get(f"{API_BASE}/jobs/{job_id}")
        if r.ok:
            job = r.json()
            st.json(job)

            # Show captcha screenshot if exists
            if job.get("captcha_screenshot"):
                path = job["captcha_screenshot"]
                st.write("Captcha screenshot saved at:", path)

                if os.path.exists(path):
                    st.image(path, caption="CAPTCHA screenshot")

                # Resume button
                if st.button("I solved CAPTCHA on Edge (Resume)"):
                    rr = requests.post(f"{API_BASE}/jobs/{job_id}/resume")
                    if rr.ok:
                        st.success("Resume called")
                        st.json(rr.json())
                    else:
                        st.error(rr.text)
        else:
            st.error("Job not found")
