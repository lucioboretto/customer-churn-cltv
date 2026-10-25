import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path


# ============================================================
# 1. PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Retention Campaign Simulator",
    page_icon="🛒",
    layout="wide"
)


# ============================================================
# 2. LOAD DATA
# ============================================================

DATA_PATH = Path("app_data/customers_scored.csv")


@st.cache_data
def load_data():
    return pd.read_csv(DATA_PATH)


customers = load_data()

STRATEGIES = {
    "Highest expected loss": "expected_loss",
    "Highest churn probability": "churn_probability",
    "Highest value (CLV)": "clv",
}

ACTIONS = {
    "1. Save now": "Account manager call + tailored offer within 2 weeks",
    "2. Protect & grow": "Loyalty programme, early access to the Q4 catalogue, cross-selling",
    "3. Automated win-back": "Automated email sequence with a time-limited discount",
    "4. Business as usual": "Standard newsletter, no incentive spend",
}


# ============================================================
# 3. HELPER FUNCTIONS
# ============================================================

def select_customers(data, column, share):
    # Select the top customers according to the chosen strategy
    n_contacts = max(1, int(len(data) * share))
    return data.nlargest(n_contacts, column)


def campaign_results(data, column, share, cost, save_rate, margin):
    # Calculate the results of a campaign for one strategy
    selected = select_customers(data, column, share)
    churners = selected[selected["churn"] == 1]
    lost_value = data.loc[data["churn"] == 1, "clv"].sum()

    saved_profit = save_rate * margin * churners["clv"].sum()
    total_cost = cost * len(selected)

    return {
        "customers_contacted": len(selected),
        "churners_reached": len(churners),
        "share_of_lost_value": churners["clv"].sum() / lost_value,
        "campaign_cost": total_cost,
        "saved_profit": saved_profit,
        "net_benefit": saved_profit - total_cost,
    }


# ============================================================
# 4. SIDEBAR - CAMPAIGN SETTINGS
# ============================================================

st.sidebar.header("Campaign settings")

strategy_name = st.sidebar.selectbox("Targeting strategy", list(STRATEGIES.keys()))
strategy_column = STRATEGIES[strategy_name]

share_contacted = st.sidebar.slider("Share of customers to contact", 0.05, 1.0, 0.20, 0.05, format="%.2f")

st.sidebar.subheader("Assumptions")
cost_per_contact = st.sidebar.number_input("Cost per contact (£)", min_value=0.0, value=15.0, step=1.0)
save_rate = st.sidebar.slider("Save rate (churners retained)", 0.05, 0.50, 0.20, 0.05)
margin = st.sidebar.slider("Gross margin", 0.10, 0.60, 0.30, 0.05)

st.sidebar.caption(
    "The assumptions are parameters on purpose: in a real project they would be agreed "
    "with the business and validated with an A/B test."
)


# ============================================================
# 5. HEADER
# ============================================================

st.title("🛒 Retention Campaign Simulator")

st.write(
    "Which customers should a retention campaign target to protect the most revenue? "
    "The default strategy ranks customers by **expected loss = churn probability × annual value**. "
    "This app uses the churn model of the project on **2,775 active customers (September 2011)** "
    "and simulates a campaign for the next 90 days."
)

st.info(
    "This is a backtest: the data is from the test period, so we know which customers really "
    "churned and can measure how much of the lost value each strategy would have reached."
)


# ============================================================
# 6. CAMPAIGN RESULTS
# ============================================================

results = campaign_results(customers, strategy_column, share_contacted, cost_per_contact, save_rate, margin)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Customers contacted", f"{results['customers_contacted']:,}")
col2.metric("Churners reached", f"{results['churners_reached']:,}")
col3.metric("Lost value reached", f"{results['share_of_lost_value']:.0%}")
col4.metric("Net benefit", f"£{results['net_benefit']:,.0f}")

st.subheader("Strategy comparison")

comparison = pd.DataFrame({
    name: campaign_results(customers, column, share_contacted, cost_per_contact, save_rate, margin)
    for name, column in STRATEGIES.items()
}).T

comparison.columns = ["Customers contacted", "Churners reached", "Lost value reached", "Campaign cost", "Profit saved", "Net benefit"]

st.dataframe(
    comparison.style.format({
        "Customers contacted": "{:,.0f}",
        "Churners reached": "{:,.0f}",
        "Lost value reached": "{:.0%}",
        "Campaign cost": "£{:,.0f}",
        "Profit saved": "£{:,.0f}",
        "Net benefit": "£{:,.0f}",
    }),
    width="stretch"
)

# Net benefit curve for each strategy
shares = np.linspace(0.01, 1, 100)

fig, ax = plt.subplots(figsize=(10, 4))

for name, column in STRATEGIES.items():
    benefits = [
        campaign_results(customers, column, s, cost_per_contact, save_rate, margin)["net_benefit"] / 1000
        for s in shares
    ]
    ax.plot(shares, benefits, label=name, linewidth=2)

ax.axvline(share_contacted, color="grey", linestyle=":", label="Selected share")
ax.axhline(0, color="grey", linewidth=1)
ax.set_title("Net Benefit by Share of Customers Contacted")
ax.set_xlabel("Share of Customers Contacted")
ax.set_ylabel("Net Benefit (£ thousands)")
ax.legend()

st.pyplot(fig)


# ============================================================
# 7. CUSTOMER SEGMENTS
# ============================================================

st.subheader("Customer segments and next best action")

segments = (
    customers
    .groupby("segment")
    .agg(
        customers=("CustomerID", "count"),
        avg_churn_probability=("churn_probability", "mean"),
        avg_annual_value=("clv", "mean"),
        revenue_at_risk=("expected_loss", "sum"),
    )
)
segments["action"] = segments.index.map(ACTIONS)

st.dataframe(
    segments.style.format({
        "avg_churn_probability": "{:.0%}",
        "avg_annual_value": "£{:,.0f}",
        "revenue_at_risk": "£{:,.0f}",
    }),
    width="stretch"
)


# ============================================================
# 8. CUSTOMER LOOKUP
# ============================================================

st.subheader("Customer lookup")

customer_id = st.selectbox(
    "Select a customer",
    customers.sort_values("expected_loss", ascending=False)["CustomerID"].tolist()
)

customer = customers[customers["CustomerID"] == customer_id].iloc[0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Churn probability", f"{customer['churn_probability']:.0%}")
c2.metric("Annual value (CLV)", f"£{customer['clv']:,.0f}")
c3.metric("Expected loss", f"£{customer['expected_loss']:,.0f}")
c4.metric("Days since last order", f"{customer['recency_days']:.0f}")

st.write(f"**Segment:** {customer['segment']}")
st.write(f"**Recommended action:** {customer['action']}")


# ============================================================
# 9. TARGET LIST
# ============================================================

st.subheader("Customers to contact")

target_list = select_customers(customers, strategy_column, share_contacted)[
    ["CustomerID", "segment", "churn_probability", "clv", "expected_loss", "action"]
]

st.dataframe(
    target_list.style.format({
        "churn_probability": "{:.0%}",
        "clv": "£{:,.0f}",
        "expected_loss": "£{:,.0f}",
    }),
    width="stretch",
    hide_index=True
)

st.download_button(
    "Download target list (CSV)",
    target_list.to_csv(index=False),
    file_name="retention_target_list.csv",
    mime="text/csv"
)

st.caption(
    "⚠️ Experimental portfolio project. The churn model predicts who is likely to leave, "
    "not who the campaign would convince to stay. The next step would be an A/B test."
)
