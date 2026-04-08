"""Streamlit Dashboard for Sandbox Pool Visualization.

This dashboard provides a graphical interface to view DynamoDB sandbox allocations
without modifying the production API broker code.

Designed for EC2 deployment in eu-central-1 using IAM roles (no access keys needed).
"""

import streamlit as st
import boto3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import time

# Page configuration
st.set_page_config(
    page_title="Sandbox Pool Dashboard",
    page_icon="🏖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #e0e0e0;
    }
    .status-badge {
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-size: 0.875rem;
        font-weight: 600;
        display: inline-block;
    }
    .status-available {
        background-color: #d4edda;
        color: #155724;
    }
    .status-allocated {
        background-color: #d1ecf1;
        color: #0c5460;
    }
    .status-pending_deletion {
        background-color: #f8d7da;
        color: #721c24;
    }
    .status-stale {
        background-color: #fff3cd;
        color: #856404;
    }
    .status-deleted {
        background-color: #e2e3e5;
        color: #383d41;
    }
    .niosxaas-cleaned {
        background-color: #d4edda;
        color: #155724;
    }
    .niosxaas-skipped {
        background-color: #e2e3e5;
        color: #383d41;
    }
    .niosxaas-failed {
        background-color: #f8d7da;
        color: #721c24;
    }
    .freshness-indicator {
        font-size: 0.875rem;
        color: #6c757d;
        font-style: italic;
    }
    </style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_dynamodb_client():
    """Initialize DynamoDB client using IAM role (no credentials needed on EC2)."""
    aws_region = os.getenv("AWS_REGION", "eu-central-1")
    table_name = os.getenv("DDB_TABLE_NAME", "sandbox-broker-pool")

    # When running on EC2 with IAM role, boto3 automatically uses instance credentials
    dynamodb = boto3.resource("dynamodb", region_name=aws_region)

    return dynamodb, table_name


@st.cache_data(ttl=30)  # Cache for 30 seconds
def fetch_all_sandboxes():
    """Fetch all sandboxes from DynamoDB."""
    dynamodb, table_name = get_dynamodb_client()
    table = dynamodb.Table(table_name)

    try:
        fetch_timestamp = time.time()
        response = table.scan()
        items = response.get("Items", [])

        # Handle pagination
        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response.get("Items", []))

        # Separate sandbox items from NIOSXaaS cleanup records
        sandbox_items = []
        niosxaas_items = []
        for item in items:
            pk = item.get("PK", "")
            if pk.startswith("NIOSXAAS#"):
                niosxaas_items.append(item)
            elif pk.startswith("SBX#"):
                sandbox_items.append(item)

        return sandbox_items, niosxaas_items, fetch_timestamp
    except Exception as e:
        st.error(f"Error fetching data from DynamoDB: {e}")
        st.error(f"Region: {os.getenv('AWS_REGION', 'eu-central-1')}, Table: {table_name}")
        return [], [], time.time()


def convert_timestamp(timestamp):
    """Convert Unix timestamp to readable date."""
    if timestamp and timestamp != 0:
        try:
            # Ensure it's a valid numeric timestamp
            ts = float(timestamp)
            # Validate it's a reasonable timestamp (after year 2000)
            if ts > 946684800:
                return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
            return "N/A"
        except (ValueError, TypeError, OSError):
            return "N/A"
    return "N/A"


def prepare_dataframe(items):
    """Convert DynamoDB items to pandas DataFrame."""
    if not items:
        return pd.DataFrame()

    def validate_timestamp(timestamp):
        """Validate that a value is a valid numeric timestamp."""
        if not timestamp:
            return None
        try:
            ts = float(timestamp)
            # Check if it's a reasonable timestamp (after year 2000)
            return ts if ts > 946684800 else None
        except (ValueError, TypeError):
            return None

    data = []
    for item in items:
        allocated_at_raw = item.get("allocated_at")
        data.append({
            "Sandbox ID": item.get("sandbox_id", "N/A"),
            "Name": item.get("name", "N/A"),
            "Status": item.get("status", "N/A"),
            "Track Name": item.get("track_name", "N/A"),
            "Allocated To Track": item.get("allocated_to_track", "N/A"),
            "External ID": item.get("external_id", "N/A"),
            "Lab Duration (hours)": item.get("lab_duration_hours", 0),
            "Allocated At": convert_timestamp(allocated_at_raw),
            "allocated_at_raw": validate_timestamp(allocated_at_raw),  # Only store valid timestamps for charting
            "Created At": convert_timestamp(item.get("created_at")),
            "Updated At": convert_timestamp(item.get("updated_at")),
            "Deletion Requested At": convert_timestamp(item.get("deletion_requested_at")),
            "Idempotency Key": item.get("idempotency_key", "N/A"),
            # NIOSXaaS cleanup tracking fields
            "NIOSXaaS Cleaned At": convert_timestamp(item.get("niosxaas_cleaned_at")),
            "niosxaas_cleaned_at_raw": item.get("niosxaas_cleaned_at"),
            "NIOSXaaS Skipped": "Yes" if item.get("niosxaas_cleanup_skipped") else "No",
            "niosxaas_cleanup_skipped_raw": item.get("niosxaas_cleanup_skipped", False),
            "NIOSXaaS Failed Reason": item.get("niosxaas_cleanup_failed_reason", "N/A") or "N/A",
            # Soft-delete tracking
            "Deleted At": convert_timestamp(item.get("deleted_at")),
            "deleted_at_raw": item.get("deleted_at"),
            # SFDC integration
            "SFDC ID": item.get("sfdc_account_id", "N/A"),
        })

    return pd.DataFrame(data)


def prepare_niosxaas_dataframe(items):
    """Convert NIOSXaaS cleanup records to pandas DataFrame."""
    if not items:
        return pd.DataFrame()

    data = []
    for item in items:
        data.append({
            "Sandbox ID": item.get("sandbox_id", "N/A"),
            "Name": item.get("sandbox_name", "N/A"),
            "External ID": item.get("external_id", "N/A"),
            "Track Name": item.get("track_name", "N/A"),
            "Allocated To Track": item.get("allocated_to_track", "N/A"),
            "NIOSXaaS Cleaned At": convert_timestamp(item.get("niosxaas_cleaned_at")),
            "niosxaas_cleaned_at_raw": item.get("niosxaas_cleaned_at"),
            "NIOSXaaS Skipped": "Yes" if item.get("niosxaas_cleanup_skipped") else "No",
            "niosxaas_cleanup_skipped_raw": item.get("niosxaas_cleanup_skipped", False),
            "NIOSXaaS Failed Reason": item.get("niosxaas_cleanup_failed_reason", "N/A") or "N/A",
            "Deleted At": convert_timestamp(item.get("deleted_at")),
            "deleted_at_raw": item.get("deleted_at"),
        })

    return pd.DataFrame(data)


def main():
    """Main dashboard application."""

    # Header
    st.markdown('<div class="main-header">🏖️ Sandbox Pool Dashboard</div>', unsafe_allow_html=True)
    st.markdown("Real-time visualization of DynamoDB sandbox allocations")

    # Fetch data
    with st.spinner("Fetching data from DynamoDB..."):
        sandbox_items, niosxaas_items, fetch_timestamp = fetch_all_sandboxes()

    # Data freshness indicator
    seconds_ago = int(time.time() - fetch_timestamp)
    if seconds_ago < 60:
        freshness_text = f"🟢 Data refreshed {seconds_ago}s ago"
    elif seconds_ago < 300:
        freshness_text = f"🟡 Data refreshed {seconds_ago//60}m {seconds_ago%60}s ago"
    else:
        freshness_text = f"🔴 Data refreshed {seconds_ago//60}m ago"

    st.markdown(f'<div class="freshness-indicator">{freshness_text}</div>', unsafe_allow_html=True)

    if not sandbox_items:
        st.warning("No sandbox data found in DynamoDB table.")
        st.info(f"Region: {os.getenv('AWS_REGION', 'eu-central-1')}")
        st.info(f"Table: {os.getenv('DDB_TABLE_NAME', 'sandbox-broker-pool')}")
        return

    df = prepare_dataframe(sandbox_items)
    niosxaas_df = prepare_niosxaas_dataframe(niosxaas_items)

    # Sidebar filters
    st.sidebar.title("⚙️ Filters")

    # Search filter
    st.sidebar.markdown("### 🔍 Search")
    search_query = st.sidebar.text_input("Search by Sandbox ID or Name", "").strip()

    if search_query:
        search_mask = (
            df["Sandbox ID"].astype(str).str.contains(search_query, case=False, na=False) |
            df["Name"].astype(str).str.contains(search_query, case=False, na=False)
        )
        df = df[search_mask]
        st.sidebar.success(f"Found {len(df)} matches")

    st.sidebar.markdown("---")

    # Status filter
    status_options = ["All"] + sorted(df["Status"].unique().tolist())
    selected_status = st.sidebar.selectbox("Filter by Status", status_options)

    # Track name filter
    track_names = df["Track Name"].dropna()
    track_names = track_names[track_names != "N/A"].unique().tolist()
    track_name_options = ["All"] + sorted(track_names)
    selected_track = st.sidebar.selectbox("Filter by Track Name", track_name_options)

    # Apply filters
    filtered_df = df.copy()
    if selected_status != "All":
        filtered_df = filtered_df[filtered_df["Status"] == selected_status]
    if selected_track != "All":
        filtered_df = filtered_df[filtered_df["Track Name"] == selected_track]

    # Auto-refresh toggle
    st.sidebar.markdown("---")
    auto_refresh = st.sidebar.checkbox("Auto-refresh (30s)", value=False)
    if auto_refresh:
        st.sidebar.info("Dashboard will refresh every 30 seconds")
        time.sleep(30)
        st.rerun()

    # Manual refresh button
    if st.sidebar.button("🔄 Refresh Now"):
        st.cache_data.clear()
        st.rerun()

    # Metrics row
    st.markdown("### 📊 Overview Metrics")
    col1, col2, col3, col4 = st.columns(4)

    total_sandboxes = len(df)
    available_count = len(df[df["Status"] == "available"])
    allocated_count = len(df[df["Status"] == "allocated"])
    pending_deletion = len(df[df["Status"] == "pending_deletion"])

    with col1:
        st.metric("Total Sandboxes", total_sandboxes)
    with col2:
        st.metric("Available", available_count, delta=f"{(available_count/total_sandboxes*100):.1f}%" if total_sandboxes > 0 else "0%")
    with col3:
        st.metric("Allocated", allocated_count, delta=f"{(allocated_count/total_sandboxes*100):.1f}%" if total_sandboxes > 0 else "0%")
    with col4:
        st.metric("Pending Deletion", pending_deletion)

    # Duration statistics
    st.markdown("### ⏱️ Duration Statistics")
    duration_col1, duration_col2, duration_col3, duration_col4 = st.columns(4)

    durations = df[df["Lab Duration (hours)"] > 0]["Lab Duration (hours)"]

    with duration_col1:
        avg_duration = durations.mean() if not durations.empty else 0
        st.metric("Avg Lab Duration", f"{avg_duration:.1f}h")
    with duration_col2:
        max_duration = durations.max() if not durations.empty else 0
        st.metric("Max Lab Duration", f"{max_duration:.0f}h")
    with duration_col3:
        min_duration = durations.min() if not durations.empty else 0
        st.metric("Min Lab Duration", f"{min_duration:.0f}h")
    with duration_col4:
        total_hours = durations.sum() if not durations.empty else 0
        st.metric("Total Lab Hours", f"{total_hours:.0f}h")

    # NIOSXaaS Cleanup Statistics (from historical cleanup records)
    st.markdown("### 🧹 NIOSXaaS Cleanup Statistics")
    niosxaas_col1, niosxaas_col2, niosxaas_col3, niosxaas_col4 = st.columns(4)

    # Count from NIOSXaaS cleanup history records (deleted sandboxes)
    if not niosxaas_df.empty:
        niosxaas_cleaned = len(niosxaas_df[
            (niosxaas_df["niosxaas_cleaned_at_raw"].notna()) &
            (niosxaas_df["niosxaas_cleanup_skipped_raw"] != True) &
            (niosxaas_df["NIOSXaaS Failed Reason"] == "N/A")
        ])
        niosxaas_skipped = len(niosxaas_df[niosxaas_df["niosxaas_cleanup_skipped_raw"] == True])
        niosxaas_failed = len(niosxaas_df[niosxaas_df["NIOSXaaS Failed Reason"] != "N/A"])
    else:
        niosxaas_cleaned = 0
        niosxaas_skipped = 0
        niosxaas_failed = 0

    # Pending count comes from active sandboxes awaiting cleanup
    niosxaas_pending = len(df[
        (df["Status"] == "pending_deletion") &
        (df["niosxaas_cleaned_at_raw"].isna() | (df["niosxaas_cleaned_at_raw"] == 0)) &
        (df["niosxaas_cleanup_skipped_raw"] != True)
    ])

    with niosxaas_col1:
        st.metric("🟢 Cleaned", niosxaas_cleaned, help="Sandboxes with NIOSXaaS services successfully deleted")
    with niosxaas_col2:
        st.metric("⚪ Skipped", niosxaas_skipped, help="Sandboxes with no NIOSXaaS services found")
    with niosxaas_col3:
        st.metric("🔴 Failed", niosxaas_failed, help="Sandboxes where NIOSXaaS cleanup failed")
    with niosxaas_col4:
        st.metric("🟡 Pending", niosxaas_pending, help="Pending deletion sandboxes awaiting NIOSXaaS cleanup")

    # Show recent NIOSXaaS cleanups
    if not niosxaas_df.empty:
        with st.expander(f"📋 View {len(niosxaas_df)} NIOSXaaS Cleanup Records"):
            display_cols = ["Sandbox ID", "Name", "Track Name", "NIOSXaaS Cleaned At", "NIOSXaaS Skipped", "NIOSXaaS Failed Reason", "Deleted At"]
            st.dataframe(niosxaas_df[display_cols], use_container_width=True, hide_index=True)

    # Show failed cleanups if any
    if niosxaas_failed > 0:
        with st.expander(f"⚠️ View {niosxaas_failed} Failed NIOSXaaS Cleanups"):
            failed_df = niosxaas_df[niosxaas_df["NIOSXaaS Failed Reason"] != "N/A"][
                ["Sandbox ID", "Name", "Track Name", "NIOSXaaS Failed Reason", "Deleted At"]
            ]
            st.dataframe(failed_df, use_container_width=True, hide_index=True)

    # Charts row
    st.markdown("### 📈 Visualizations")
    chart_col1, chart_col2, chart_col3, chart_col4 = st.columns(4)

    with chart_col1:
        # Status distribution pie chart
        st.markdown("#### Status Distribution")
        status_counts = df["Status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]

        fig_pie = px.pie(
            status_counts,
            values="Count",
            names="Status",
            color="Status",
            color_discrete_map={
                "available": "#2ecc71",
                "allocated": "#3498db",
                "pending_deletion": "#e74c3c",
                "stale": "#f39c12",
                "deletion_failed": "#9b59b6",
                "deleted": "#7f8c8d"
            }
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)

    with chart_col2:
        # Track name distribution (only allocated)
        st.markdown("#### Allocations by Track Name")
        allocated_df = df[df["Status"] == "allocated"]
        if not allocated_df.empty and "Track Name" in allocated_df.columns:
            track_counts = allocated_df["Track Name"].value_counts().reset_index()
            track_counts.columns = ["Track Name", "Count"]
            track_counts = track_counts[track_counts["Track Name"] != "N/A"]

            if not track_counts.empty:
                fig_bar = px.bar(
                    track_counts,
                    x="Track Name",
                    y="Count",
                    color="Count",
                    color_continuous_scale="Blues"
                )
                fig_bar.update_layout(showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("No track name data available for allocated sandboxes")
        else:
            st.info("No allocated sandboxes with track names")

    with chart_col3:
        # Allocation timeline
        st.markdown("#### Allocation Timeline (24h)")
        allocated_df = df[df["allocated_at_raw"].notna()].copy()

        if not allocated_df.empty:
            # Filter to only numeric timestamps (exclude invalid data)
            def is_valid_timestamp(val):
                try:
                    # Check if value is numeric and represents a reasonable timestamp
                    ts = float(val)
                    # Timestamps should be positive and reasonable (after year 2000)
                    return ts > 946684800  # Jan 1, 2000 in Unix timestamp
                except (ValueError, TypeError):
                    return False

            allocated_df = allocated_df[allocated_df["allocated_at_raw"].apply(is_valid_timestamp)].copy()

            if not allocated_df.empty:
                # Convert string timestamps to numeric, then to datetime
                allocated_df["allocated_datetime"] = pd.to_datetime(
                    pd.to_numeric(allocated_df["allocated_at_raw"], errors='coerce'),
                    unit='s',
                    errors='coerce'
                )

                # Drop rows where conversion failed
                allocated_df = allocated_df[allocated_df["allocated_datetime"].notna()]

                if not allocated_df.empty:
                    # Filter last 24 hours
                    cutoff_time = datetime.now() - timedelta(hours=24)
                    recent_allocations = allocated_df[allocated_df["allocated_datetime"] > cutoff_time]

                    if not recent_allocations.empty:
                        # Group by hour
                        recent_allocations["hour"] = recent_allocations["allocated_datetime"].dt.floor('H')
                        hourly_counts = recent_allocations.groupby("hour").size().reset_index(name="count")

                        fig_timeline = px.line(
                            hourly_counts,
                            x="hour",
                            y="count",
                            markers=True,
                            labels={"hour": "Time", "count": "Allocations"}
                        )
                        fig_timeline.update_layout(showlegend=False, xaxis_title="", yaxis_title="Count")
                        st.plotly_chart(fig_timeline, use_container_width=True)
                    else:
                        st.info("No allocations in the last 24 hours")
                else:
                    st.info("No valid allocation timestamps available")
            else:
                st.info("No valid allocation timestamps available")
        else:
            st.info("No allocation data available")

    with chart_col4:
        # NIOSXaaS cleanup status distribution
        st.markdown("#### NIOSXaaS Cleanup")
        niosxaas_data = [
            {"Status": "Cleaned", "Count": niosxaas_cleaned},
            {"Status": "Skipped", "Count": niosxaas_skipped},
            {"Status": "Failed", "Count": niosxaas_failed},
            {"Status": "Pending", "Count": niosxaas_pending},
        ]
        niosxaas_df = pd.DataFrame(niosxaas_data)
        niosxaas_df = niosxaas_df[niosxaas_df["Count"] > 0]  # Only show non-zero

        if not niosxaas_df.empty:
            fig_niosxaas = px.pie(
                niosxaas_df,
                values="Count",
                names="Status",
                color="Status",
                color_discrete_map={
                    "Cleaned": "#2ecc71",
                    "Skipped": "#95a5a6",
                    "Failed": "#e74c3c",
                    "Pending": "#f39c12"
                }
            )
            fig_niosxaas.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_niosxaas, use_container_width=True)
        else:
            st.info("No NIOSXaaS cleanup data yet")

    # Allocation mapping table
    st.markdown("### 🗺️ Track Name ↔ Allocated To Track Mapping")
    st.markdown("Shows the relationship between **track_name** and **allocated_to_track** for allocated sandboxes")

    mapping_df = df[df["Status"] == "allocated"][["Name", "Track Name", "Allocated To Track", "Allocated At", "External ID"]].copy()
    mapping_df = mapping_df[mapping_df["Track Name"] != "N/A"]

    if not mapping_df.empty:
        st.dataframe(
            mapping_df,
            use_container_width=True,
            hide_index=True
        )

        # Summary statistics
        st.markdown("#### Mapping Summary")
        summary_col1, summary_col2 = st.columns(2)

        with summary_col1:
            unique_tracks = mapping_df["Allocated To Track"].nunique()
            st.info(f"**Unique Tracks with Allocations:** {unique_tracks}")

        with summary_col2:
            unique_track_names = mapping_df["Track Name"].nunique()
            st.info(f"**Unique Track Names:** {unique_track_names}")
    else:
        st.warning("No allocated sandboxes with track name mappings found")

    # Full data table
    st.markdown("### 📋 All Sandboxes (Filtered)")
    st.markdown(f"Showing **{len(filtered_df)}** of **{len(df)}** sandboxes")

    # Remove internal columns from display options
    internal_cols = ["allocated_at_raw", "niosxaas_cleaned_at_raw", "niosxaas_cleanup_skipped_raw", "deleted_at_raw"]
    display_options = [col for col in filtered_df.columns if col not in internal_cols]

    # Column selection
    display_columns = st.multiselect(
        "Select columns to display (click column headers to sort ↕️)",
        options=display_options,
        default=["Sandbox ID", "Name", "Status", "Track Name", "Allocated To Track", "Allocated At"]
    )

    if display_columns:
        st.dataframe(
            filtered_df[display_columns],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Select at least one column to display")

    # Download button
    csv = filtered_df.to_csv(index=False)
    st.download_button(
        label="📥 Download as CSV",
        data=csv,
        file_name=f"sandbox_pool_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )

    # Footer
    st.markdown("---")
    st.markdown(
        f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
        f"**Total Records:** {len(df)} | "
        f"**Region:** {os.getenv('AWS_REGION', 'eu-central-1')}"
    )


if __name__ == "__main__":
    main()
