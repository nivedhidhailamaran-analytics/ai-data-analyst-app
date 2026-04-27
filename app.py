import streamlit as st
import pandas as pd
from openai import OpenAI
import os

# 🔹 API KEY
os.environ["OPENAI_API_KEY"] = "myapikey"
client = OpenAI()


# 🔹 -------- COLUMN DETECTION --------
def detect_columns(df):
    id_col, date_col = None, None

    id_keywords = ["id", "customer", "order", "user", "serial"]
    date_keywords = ["date", "time"]

    for col in df.columns:
        col_lower = col.lower()

        if any(k in col_lower for k in id_keywords) and id_col is None:
            id_col = col

        if any(k in col_lower for k in date_keywords) and date_col is None:
            date_col = col

    numeric_cols = df.select_dtypes(include=["int64", "float64"]).columns.tolist()
    categorical_cols = df.select_dtypes(include=["object"]).columns.tolist()

    # 🔥 REMOVE ID FROM NUMERIC
    if id_col and id_col in numeric_cols:
        numeric_cols.remove(id_col)

    return id_col, date_col, numeric_cols, categorical_cols


# 🔹 -------- CLEANING --------
@st.cache_data
def clean_data(df):
    df = df.copy()

    id_col, date_col, numeric_cols, categorical_cols = detect_columns(df)

    # Limit size
    if len(df) > 50000:
        df = df.sample(50000)

    # Date conversion
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    # Fill numeric
    for col in numeric_cols:
        df[col] = df[col].fillna(df[col].median())

    # Fill categorical
    for col in categorical_cols:
        df[col] = df[col].fillna("Unknown")

    # Outlier handling (EXCLUDE ID)
    for col in numeric_cols:
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        df[col] = df[col].clip(Q1 - 1.5 * IQR, Q3 + 1.5 * IQR)

    df = df.drop_duplicates()

    return df


# 🔹 -------- SUMMARY --------
def build_summary(df):
    summary = {}

    id_col, date_col, numeric_cols, categorical_cols = detect_columns(df)

    # Customers (ONLY place ID used)
    if id_col:
        summary["total_entities"] = int(df[id_col].nunique())

    # Numeric KPIs
    for col in numeric_cols:
        summary[f"{col}_total"] = float(df[col].sum())
        summary[f"{col}_avg"] = float(df[col].mean())

    # Category analysis
    for cat in categorical_cols:
        for num in numeric_cols:
            grouped = df.groupby(cat)[num].sum().sort_values(ascending=False)
            summary[f"top_{cat}_{num}"] = grouped.head(3).to_dict()

    # Time trends
    if date_col:
        df["year"] = df[date_col].dt.year

        for num in numeric_cols:
            summary[f"{num}_yearly"] = df.groupby("year")[num].sum().to_dict()

    return summary


# 🔹 -------- GPT --------
def generate_ai_insights(summary):
    prompt = f"""
You are a senior business analyst.

Provide:

### Key Insights
### Observations
### Risks
### Business Recommendations

Be specific and business-focused.

Data:
{summary}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a strict business analyst."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=800
    )

    return response.choices[0].message.content


# 🔹 -------- UI --------
st.title("📊 AI Data Analyst App (Final)")
st.write("Upload your dataset and get insights")

uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])

if uploaded_file is not None:

    df = pd.read_csv(uploaded_file, encoding="latin1")

    st.write("### 📄 Raw Data")
    st.dataframe(df.head())

    if st.button("🔍 Run Analysis"):

        with st.spinner("Processing..."):

            clean_df = clean_data(df)

            st.write("### 🧹 Cleaned Data")
            st.dataframe(clean_df.head())

            id_col, date_col, numeric_cols, categorical_cols = detect_columns(clean_df)

            # 🔥 KPI SECTION (NO ID HERE)
            st.write("## 📌 Key Metrics")

            for col in numeric_cols:
                st.metric(f"{col} Total", round(clean_df[col].sum(), 2))

            if id_col:
                st.metric("Total Entities", clean_df[id_col].nunique())

            # 🔥 CHARTS (NO ID USED)
            for cat in categorical_cols:
                for num in numeric_cols:
                    st.write(f"### 📊 {num} by {cat}")
                    grouped = clean_df.groupby(cat)[num].sum().sort_values(ascending=False)
                    st.bar_chart(grouped)

            # 🔥 TIME TREND
            if date_col:
                for num in numeric_cols:
                    st.write(f"### 📈 {num} Trend")
                    trend = clean_df.groupby(clean_df[date_col])[num].sum()
                    st.line_chart(trend)

            # 🔹 GPT
            summary = build_summary(clean_df)

            st.write("🤖 Generating insights...")
            ai_output = generate_ai_insights(summary)

            st.write("## 💡 AI Insights")
            st.write(ai_output)