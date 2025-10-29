import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Transaction Data Cleaner", page_icon="🧹", layout="wide")

# Title and description
st.title("🧹 Transaction Data Cleaner & Discount Allocator")
st.markdown("""
Upload your transaction CSV to allocate discounts proportionally by item value.
This tool removes duplicate rows and calculates proper discount allocation for profitability analysis.
""")

# File upload
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

def clean_transaction_data(df):
    """Clean and process transaction data with proportional discount allocation"""
    
    # Create a unique key for each item in each order
    df['unique_key'] = df['order_number'].astype(str) + '_' + df['item_ref_id'].astype(str)
    
    # Separate rows with and without discounts
    discount_rows = df[df['discountName'].notna()].copy()
    base_rows = df[df['discountName'].isna()].copy()
    
    # If no base rows, use discount rows as base
    if len(base_rows) == 0:
        base_rows = df.copy()
    
    # Group by unique_key to get one row per item
    base_rows = base_rows.groupby('unique_key').first().reset_index()
    
    cleaned_data = []
    
    for _, base_row in base_rows.iterrows():
        order_number = base_row['order_number']
        item_ref_id = base_row['item_ref_id']
        
        # Get discount info for this item if exists
        discount_info = discount_rows[
            (discount_rows['order_number'] == order_number) & 
            (discount_rows['item_ref_id'] == item_ref_id)
        ]
        
        # Get all items in this order (from base rows)
        order_items = base_rows[base_rows['order_number'] == order_number]
        
        # Calculate order totals
        order_items_total = (order_items['myr_item_unit_amount'] * order_items['item_quantity']).sum()
        
        # Current item values
        item_price = float(base_row['myr_item_unit_amount'])
        quantity = float(base_row['item_quantity'])
        item_total = item_price * quantity
        
        # Calculate proportional discount
        item_proportion = item_total / order_items_total if order_items_total > 0 else 0
        
        # Calculate total order discount
        total_order_discount = 0
        for _, order_item in order_items.iterrows():
            item_val = float(order_item['myr_item_unit_amount']) * float(order_item['item_quantity'])
            # Find matching discount row
            matching_discount = discount_rows[
                (discount_rows['order_number'] == order_number) & 
                (discount_rows['item_ref_id'] == order_item['item_ref_id'])
            ]
            if len(matching_discount) > 0:
                paid_val = float(order_item['myr_paid_amount'])
                total_order_discount += (item_val - paid_val)
        
        # Allocate discount proportionally
        allocated_discount = total_order_discount * item_proportion
        
        # Get points redeemed
        points_redeemed = float(base_row['myr_points_redeemed_value']) if pd.notna(base_row['myr_points_redeemed_value']) else 0
        
        # Calculate final paid amount
        final_paid_amount = item_total - allocated_discount - points_redeemed
        
        # Get discount name if exists
        discount_name = discount_info['discountName'].iloc[0] if len(discount_info) > 0 else ''
        
        cleaned_data.append({
            'created_at_myt': base_row['created_at_myt'],
            'order_number': order_number,
            'customer_email': base_row['customer_email'],
            'CarrierCode': base_row['CarrierCode'],
            'item_name': base_row['item_name'],
            'item_ref_id': item_ref_id,
            'item_quantity': quantity,
            'item_unit_price': item_price,
            'item_total_price': item_total,
            'discount_name': discount_name,
            'discount_amount': allocated_discount,
            'points_redeemed': points_redeemed,
            'final_paid_amount': final_paid_amount,
            'order_total': float(base_row['myr_total_amount']),
            'item_proportion_pct': round(item_proportion * 100, 2)
        })
    
    return pd.DataFrame(cleaned_data)

if uploaded_file is not None:
    try:
        # Read the CSV
        df = pd.read_csv(uploaded_file)
        
        st.success(f"✅ File uploaded successfully! Found {len(df)} rows")
        
        # Show original data info
        with st.expander("📊 Original Data Preview"):
            st.dataframe(df.head(10))
            st.write(f"Total rows: {len(df)}")
            st.write(f"Columns: {', '.join(df.columns)}")
        
        # Clean the data
        with st.spinner("Cleaning data..."):
            cleaned_df = clean_transaction_data(df)
        
        st.success(f"✅ Data cleaned! Reduced to {len(cleaned_df)} unique items")
        
        # Calculate statistics
        st.subheader("📈 Summary Statistics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Orders", cleaned_df['order_number'].nunique())
            st.metric("Total Items", int(cleaned_df['item_quantity'].sum()))
        
        with col2:
            st.metric("Total Revenue", f"RM {cleaned_df['item_total_price'].sum():,.2f}")
            st.metric("Total Discounts", f"RM {cleaned_df['discount_amount'].sum():,.2f}")
        
        with col3:
            st.metric("Points Redeemed", f"RM {cleaned_df['points_redeemed'].sum():,.2f}")
            st.metric("Total Paid", f"RM {cleaned_df['final_paid_amount'].sum():,.2f}")
        
        with col4:
            avg_discount_pct = (cleaned_df['discount_amount'].sum() / cleaned_df['item_total_price'].sum() * 100)
            st.metric("Avg Discount %", f"{avg_discount_pct:.2f}%")
            st.metric("Unique Products", cleaned_df['item_ref_id'].nunique())
        
        # Display cleaned data
        st.subheader("🧹 Cleaned Data Preview")
        
        # Format display columns
        display_df = cleaned_df.copy()
        display_df['item_unit_price'] = display_df['item_unit_price'].apply(lambda x: f"{x:.2f}")
        display_df['item_total_price'] = display_df['item_total_price'].apply(lambda x: f"{x:.2f}")
        display_df['discount_amount'] = display_df['discount_amount'].apply(lambda x: f"{x:.2f}")
        display_df['points_redeemed'] = display_df['points_redeemed'].apply(lambda x: f"{x:.2f}")
        display_df['final_paid_amount'] = display_df['final_paid_amount'].apply(lambda x: f"{x:.2f}")
        
        st.dataframe(
            display_df.head(20),
            use_container_width=True,
            height=400
        )
        
        # Download button
        st.subheader("💾 Download Cleaned Data")
        
        # Convert to CSV
        csv = cleaned_df.to_csv(index=False)
        
        st.download_button(
            label="⬇️ Download Cleaned CSV",
            data=csv,
            file_name="cleaned_transactions.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        # Additional insights
        st.subheader("🔍 Additional Insights")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Top 10 Products by Revenue**")
            top_products = cleaned_df.groupby('item_name')['item_total_price'].sum().sort_values(ascending=False).head(10)
            st.dataframe(top_products.reset_index().rename(columns={'item_name': 'Product', 'item_total_price': 'Revenue'}))
        
        with col2:
            st.write("**Top 10 Discount Codes Used**")
            top_discounts = cleaned_df[cleaned_df['discount_name'] != ''].groupby('discount_name')['discount_amount'].sum().sort_values(ascending=False).head(10)
            if len(top_discounts) > 0:
                st.dataframe(top_discounts.reset_index().rename(columns={'discount_name': 'Discount Code', 'discount_amount': 'Total Discount'}))
            else:
                st.write("No discount codes found")
        
    except Exception as e:
        st.error(f"❌ Error processing file: {str(e)}")
        st.write("Please make sure your CSV has the required columns.")

else:
    # Show explanation when no file is uploaded
    st.info("👆 Please upload a CSV file to get started")
    
    st.subheader("How it works:")
    st.markdown("""
    1. **Removes duplicate rows** created by discount tracking
    2. **Allocates discounts proportionally** based on each item's contribution to order total
    3. **Formula**: `Item Discount = Total Order Discount × (Item Value / Order Total Value)`
    4. **Maintains points redemption** values separately
    5. **Calculates final paid amount**: `Item Total - Allocated Discount - Points Redeemed`
    
    ### Expected CSV Columns:
    - `created_at_myt` - Transaction date
    - `order_number` - Order ID
    - `customer_email` - Customer email
    - `CarrierCode` - Carrier code
    - `item_name` - Product name
    - `item_ref_id` - Product ID
    - `item_quantity` - Quantity
    - `myr_item_unit_amount` - Unit price
    - `myr_total_amount` - Order total
    - `myr_paid_amount` - Amount paid
    - `myr_points_redeemed_value` - Points used
    - `discountName` - Discount code applied
    """)
    
    st.subheader("Output Structure:")
    st.markdown("""
    The cleaned data will have one row per item with:
    - `item_unit_price` - Original price per unit
    - `item_total_price` - Price × Quantity
    - `discount_amount` - Proportionally allocated discount
    - `points_redeemed` - Points used
    - `final_paid_amount` - What was actually paid
    - `item_proportion_pct` - % contribution to order total
    
    Perfect for profitability analysis! 📊
    """)
