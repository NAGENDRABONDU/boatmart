from flask import Flask, render_template, redirect, request, session
from db import get_connection

app = Flask(__name__)
app.secret_key = "boatmart_secret_key"


@app.context_processor
def inject_counts():

    cart_count = len(session.get("cart", []))

    pending_orders_count = 0

    if "user_id" in session:

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
        SELECT COUNT(*)
        FROM orders
        WHERE user_id = ?
        AND status = 'Preparing'
    """, (session["user_id"],))

        pending_orders_count = cursor.fetchone()[0]

        conn.close()

    return {
        "cart_count": cart_count,
        "pending_orders_count": pending_orders_count
    }


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        mobile = request.form["mobile"]
        password = request.form["password"]

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                user_id,
                boat_id,
                role,
                status,
                is_admin
            FROM users
            WHERE mobile = ?
            AND password = ?
        """, (mobile, password))

        user = cursor.fetchone()

        conn.close()

        if not user:
        
            return render_template(
                "invalid_login.html"
            )

        if user[3] == "pending":
        
            return render_template(
                "approval_pending.html"
            )
        if user[3] == "rejected":

            return render_template(
                "rejected_user.html"
            )

        session["user_id"] = user[0]
        session["boat_id"] = user[1]
        session["role"] = user[2]
        session["is_admin"] = user[4]

        return redirect("/products")

    return render_template("login.html")


@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        mobile = request.form["mobile"]
        password = request.form["password"]

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id
            FROM users
            WHERE mobile = ?
            AND password = ?
            AND is_admin = 1
        """, (
            mobile,
            password
        ))

        admin = cursor.fetchone()

        conn.close()

        if admin:

            session["admin_id"] = admin[0]

            return redirect("/admin/orders")

        return render_template(
            "invalid_admin_login.html"
        )

    return render_template(
        "admin_login.html"
    )


@app.route("/admin-logout")
def admin_logout():

    session.pop("admin_id", None)

    return redirect("/admin-login")



@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        boat_number = request.form["boat_number"]
        name = request.form["name"]
        mobile = request.form["mobile"]
        password = request.form["password"]

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT boat_id
            FROM boats
            WHERE boat_number = ?
        """, (boat_number,))

        boat = cursor.fetchone()

        if not boat:
            conn.close()
            return render_template(
                 "boat_not_found.html"
             )
        boat_id = boat[0]

        # Check mobile already exists

        cursor.execute("""
            SELECT COUNT(*)
            FROM users
            WHERE mobile = ?
        """, (mobile,))

        exists = cursor.fetchone()[0]

        if exists > 0:
        
            conn.close()

            return render_template(
                "mobile_exists.html",
                retry_url="/register"
            )

        cursor.execute("""
            INSERT INTO users
            (
                boat_id,
                name,
                mobile,
                password,
                role,
                status,
                approved_by_owner
            )
            VALUES
            (
                ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            boat_id,
            name,
            mobile,
            password,
            "crew",
            "pending",
            0
        ))

        conn.commit()
        conn.close()

        return render_template(
            "registration_pending.html"
        )

    return render_template("register.html")


@app.route("/owner-register", methods=["GET", "POST"])
def owner_register():

    if request.method == "POST":

        owner_name = request.form["owner_name"]
        boat_number = request.form["boat_number"]
        mobile = request.form["mobile"]
        password = request.form["password"]

        conn = get_connection()
        cursor = conn.cursor()

        # Check Mobile Already Exists

        cursor.execute("""
            SELECT COUNT(*)
            FROM users
            WHERE mobile = ?
        """, (mobile,))

        mobile_exists = cursor.fetchone()[0]

        if mobile_exists > 0:

            conn.close()

            return render_template(
                "mobile_exists.html",
                 retry_url="/owner-register"
            )

        # Check Boat Already Exists

        cursor.execute("""
            SELECT COUNT(*)
            FROM boats
            WHERE boat_number = ?
        """, (boat_number,))

        boat_exists = cursor.fetchone()[0]

        if boat_exists > 0:

            conn.close()

            return render_template(
                "boat_already_registered.html"
            )

        # Create Boat

        cursor.execute("""
            INSERT INTO boats
            (
                boat_number,
                owner_name,
                owner_mobile
            )
            VALUES
            (
                ?, ?, ?
            )
        """, (
            boat_number,
            owner_name,
            mobile
        ))

        conn.commit()

        # Get New Boat ID

        cursor.execute("""
            SELECT boat_id
            FROM boats
            WHERE boat_number = ?
        """, (boat_number,))

        boat = cursor.fetchone()

        boat_id = boat[0]

        # Create Owner Account

        cursor.execute("""
            INSERT INTO users
            (
                boat_id,
                name,
                mobile,
                password,
                role,
                status
            )
            VALUES
            (
                ?, ?, ?, ?, ?, ?
            )
        """, (
            boat_id,
            owner_name,
            mobile,
            password,
            "owner",
            "active"
        ))

        conn.commit()
        conn.close()

        return render_template(
            "owner_registration_success.html"
        )

    return render_template(
        "owner_register.html"
    )



@app.route("/admin/pending-users")
def pending_users():
    if "user_id" not in session:
        return redirect("/login")
    boat_id = session["boat_id"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            u.user_id,
            u.name,
            u.mobile,
            b.boat_number
        FROM users u
        JOIN boats b
            ON u.boat_id = b.boat_id
        WHERE u.status = 'pending'
        AND u.boat_id = ?
    """, (boat_id,))

    rows = cursor.fetchall()

    users = []

    for row in rows:

        users.append({
            "user_id": row[0],
            "name": row[1],
            "mobile": row[2],
            "boat_number": row[3]
        })

    conn.close()

    return render_template(
        "pending_users.html",
        users=users
    )


@app.route("/approve-user/<int:user_id>")
def approve_user(user_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET
            status = 'active',
            approved_by_owner = 1
        WHERE user_id = ?
    """, (user_id,))

    conn.commit()
    conn.close()

    return redirect("/admin/pending-users")


@app.route("/reject-user/<int:user_id>")
def reject_user(user_id):

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "owner":
        return redirect("/products")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET status = 'rejected'
        WHERE user_id = ?
    """, (user_id,))

    conn.commit()
    conn.close()

    return redirect("/admin/pending-users")


@app.route("/add-to-cart/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):

    if "user_id" not in session:
        return redirect("/login")
    user_id = session["user_id"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT cart_id, quantity
        FROM cart
        WHERE user_id = ?
        AND product_id = ?
    """, (user_id, product_id))

    item = cursor.fetchone()

    if item:
    
        cart_quantity = item[1]
    
        cursor.execute("""
            SELECT stock
            FROM products
            WHERE product_id = ?
        """, (product_id,))
    
        stock = cursor.fetchone()[0]
    
        if cart_quantity >= stock:
        
            conn.close()
    
            return render_template(
                "stock_error.html",
                message=f"We currently have only {stock} item(s) in stock. You cannot add more of this product right now."
            )
    
        cursor.execute("""
            UPDATE cart
            SET quantity = quantity + 1
            WHERE cart_id = ?
        """, (item[0],))

    else:

        cursor.execute("""
            INSERT INTO cart
            (
                user_id,
                product_id,
                quantity
            )
            VALUES
            (
                ?, ?, 1
            )
        """, (user_id, product_id))

    conn.commit()
    conn.close()

    return redirect("/products")


@app.route("/")
def home():
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM products")
        count = cursor.fetchone()[0]

        conn.close()

        return f"Database Connected Successfully. Products: {count}"

    except Exception as e:
        return str(e)


@app.route("/products")
def products():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    conn = get_connection()
    cursor = conn.cursor()
    category = request.args.get("category")
    if category:
    
        cursor.execute("""
            SELECT
                product_id,
                product_name,
                category,
                price,
                stock
            FROM products
            WHERE category = ?
        """, (category,))
    
    else:
    
        cursor.execute("""
            SELECT
                product_id,
                product_name,
                category,
                price,
                stock
            FROM products
            WHERE is_active = 1
        """)

    rows = cursor.fetchall()

    products = []

    for row in rows:

        cursor.execute("""
            SELECT ISNULL(SUM(quantity), 0)
            FROM cart
            WHERE user_id = ?
            AND product_id = ?
        """, (
            user_id,
            row[0]
        ))

        cart_qty = cursor.fetchone()[0]

        available_stock = row[4] - cart_qty

        products.append({
            "product_id": row[0],
            "product_name": row[1],
            "category": row[2],
            "price": row[3],
            "stock": row[4],
            "available_stock": available_stock
        })

    cursor.execute("""
        SELECT ISNULL(SUM(quantity), 0)
        FROM cart
        WHERE user_id = ?
    """, (user_id,))

    cart_count = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "products.html",
        products=products,
        cart_count=cart_count
    )



@app.route("/cart")
def cart():
    if "user_id" not in session:
        return redirect("/login")
    user_id = session["user_id"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            c.cart_id,
            p.product_name,
            p.price,
            c.quantity
        FROM cart c
        JOIN products p
            ON c.product_id = p.product_id
        WHERE c.user_id = ?
    """, (user_id,))

    rows = cursor.fetchall()

    cart_items = []

    total = 0

    for row in rows:

        subtotal = row[2] * row[3]

        total += subtotal

        cart_items.append({
    "cart_id": row[0],
    "product_name": row[1],
    "price": row[2],
    "quantity": row[3],
    "subtotal": subtotal
})

    conn.close()

    return render_template(
        "cart.html",
        cart_items=cart_items,
        total=total
    )


@app.route("/increase/<int:cart_id>")
def increase(cart_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            c.quantity,
            p.stock
        FROM cart c
        JOIN products p
            ON c.product_id = p.product_id
        WHERE c.cart_id = ?
    """, (cart_id,))

    item = cursor.fetchone()

    cart_quantity = item[0]
    stock = item[1]

    if cart_quantity >= stock:

        conn.close()

        return redirect("/cart?stock_limit=1")

    cursor.execute("""
        UPDATE cart
        SET quantity = quantity + 1
        WHERE cart_id = ?
    """, (cart_id,))

    conn.commit()
    conn.close()

    return redirect("/cart")


@app.route("/decrease/<int:cart_id>")
def decrease(cart_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE cart
        SET quantity = quantity - 1
        WHERE cart_id = ?
        AND quantity > 1
    """, (cart_id,))

    conn.commit()
    conn.close()

    return redirect("/cart")


@app.route("/remove/<int:cart_id>")
def remove(cart_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM cart
        WHERE cart_id = ?
    """, (cart_id,))

    conn.commit()
    conn.close()

    return redirect("/cart")


@app.route("/checkout")
def checkout():

   
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    boat_id = session["boat_id"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            c.product_id,
            p.price,
            c.quantity
        FROM cart c
        JOIN products p
            ON c.product_id = p.product_id
        WHERE c.user_id = ?
    """, (user_id,))

    cart_items = cursor.fetchall()

    if not cart_items:
        conn.close()
        return redirect("/cart")

    total_amount = 0

    for item in cart_items:
        total_amount += item[1] * item[2]

    if total_amount <= 0:
        conn.close()
        return redirect("/cart")

    # Check stock

    for item in cart_items:

        cursor.execute("""
            SELECT stock
            FROM products
            WHERE product_id = ?
        """, (item[0],))

        stock = cursor.fetchone()[0]

        if stock <= 0:
        
            conn.close()
        
            return render_template(
                "stock_error.html",
                message="This product is currently out of stock."
            )
        
        if stock < item[2]:
        
            conn.close()
        
            return render_template(
                "stock_error.html",
                message=f"Only {stock} item(s) available. Please reduce the quantity in your cart."
            )
    # Create Order

    cursor.execute("""
        INSERT INTO orders
        (
            boat_id,
            user_id,
            total_amount,
            status
        )
        VALUES (?, ?, ?, ?)
    """, (
        boat_id,
        user_id,
        total_amount,
        "Preparing"
    ))

    conn.commit()

    cursor.execute("SELECT @@IDENTITY")

    order_id = cursor.fetchone()[0]

    # Save Order Items

    for item in cart_items:

        cursor.execute("""
            INSERT INTO order_items
            (
                order_id,
                product_id,
                quantity,
                price
            )
            VALUES (?, ?, ?, ?)
        """, (
            order_id,
            item[0],
            item[2],
            item[1]
        ))

        cursor.execute("""
            UPDATE products
            SET stock = stock - ?
            WHERE product_id = ?
        """, (
            item[2],
            item[0]
        ))

    cursor.execute("""
        DELETE FROM cart
        WHERE user_id = ?
    """, (user_id,))

    conn.commit()
    conn.close()

    return render_template("order_success.html")


@app.route("/my-orders")
def my_orders():

    if "user_id" not in session:
        return redirect("/login")
    user_id = session["user_id"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            order_id,
            total_amount,
            status,
            order_date
        FROM orders
        WHERE user_id = ?
        ORDER BY order_date DESC
    """, (user_id,))

    rows = cursor.fetchall()

    orders = []

    for row in rows:

        orders.append({
            "order_id": row[0],
            "total_amount": row[1],
            "status": row[2],
            "order_date": row[3]
        })

    conn.close()

    return render_template(
        "my_orders.html",
        orders=orders
    )


@app.route("/admin/orders")
def admin_orders():

    if "admin_id" not in session:
        return redirect("/admin-login")

    conn = get_connection()
    cursor = conn.cursor()


    # Active Orders
    
    cursor.execute("""
        SELECT COUNT(*)
        FROM orders
        WHERE status IN (
            'Preparing',
            'Ready For Pickup'
        )
    """)
    
    total_orders = cursor.fetchone()[0]

    # Today's Revenue

    cursor.execute("""
        SELECT ISNULL(SUM(total_amount), 0)
        FROM orders
        WHERE status = 'Collected'
        AND CAST(order_date AS DATE) =
            CAST(GETDATE() AS DATE)
    """)

    total_revenue = cursor.fetchone()[0]


    # Total Products

    cursor.execute("""
        SELECT COUNT(*)
        FROM products
    """)

    total_products = cursor.fetchone()[0]

    # Low Stock Count

    cursor.execute("""
        SELECT COUNT(*)
        FROM products
        WHERE stock < 20
    """)
    low_stock = cursor.fetchone()[0]

    # Low Stock Products List

    cursor.execute("""
        SELECT
            product_name,
            stock
        FROM products
        WHERE stock < 20
        ORDER BY stock ASC
    """)

    low_stock_products = cursor.fetchall()

    # Orders List

    cursor.execute("""
        SELECT
            o.order_id,
            u.name,
            o.total_amount,
            o.status,
            o.order_date
        FROM orders o
        JOIN users u
            ON o.user_id = u.user_id
        WHERE o.status != 'Collected'
        ORDER BY o.order_date DESC
    """)

    rows = cursor.fetchall()

    orders = []

    for row in rows:

        orders.append({
            "order_id": row[0],
            "customer_name": row[1],
            "total_amount": row[2],
            "status": row[3],
            "order_date": row[4]
        })

    conn.close()

    return render_template(
        "admin_orders.html",
        orders=orders,
        total_orders=total_orders,
        total_revenue=total_revenue,
        total_products=total_products,
        low_stock=low_stock,
        low_stock_products=low_stock_products
    )


@app.route("/admin/products")
def admin_products():

    if "admin_id" not in session:
        return redirect("/admin-login")

    search = request.args.get("search", "")
    category = request.args.get("category", "")

    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT
            product_id,
            product_name,
            category,
            price,
            stock,
            is_active
        FROM products
        WHERE 1 = 1
    """

    params = []

    if search:

        query += """
            AND product_name LIKE ?
        """

        params.append(f"%{search}%")

    if category:

        query += """
            AND category = ?
        """

        params.append(category)

    query += """
    ORDER BY is_active ASC,
            stock ASC,
             product_name
    """

    cursor.execute(query, params)

    products = cursor.fetchall()

    conn.close()

    return render_template(
        "admin_products.html",
        products=products,
        search=search,
        category=category
    )


@app.route("/admin/disable-product/<int:product_id>")
def disable_product(product_id):

    if "admin_id" not in session:
        return redirect("/admin-login")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE products
        SET is_active = 0
        WHERE product_id = ?
    """, (product_id,))

    conn.commit()
    conn.close()

    return redirect("/admin/products")


@app.route("/admin/enable-product/<int:product_id>")
def enable_product(product_id):

    if "admin_id" not in session:
        return redirect("/admin-login")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE products
        SET is_active = 1
        WHERE product_id = ?
    """, (product_id,))

    conn.commit()
    conn.close()

    return redirect("/admin/products")


@app.route("/admin/update-stock/<int:product_id>",
           methods=["GET", "POST"])
def update_stock(product_id):

    if "admin_id" not in session:
        return redirect("/admin-login")

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":

        stock = request.form["stock"]

        cursor.execute("""
            UPDATE products
            SET stock = ?
            WHERE product_id = ?
        """, (
            stock,
            product_id
        ))

        conn.commit()
        conn.close()

        return redirect("/admin/products")

    cursor.execute("""
        SELECT
            product_name,
            stock
        FROM products
        WHERE product_id = ?
    """, (product_id,))

    product = cursor.fetchone()

    conn.close()

    return render_template(
        "update_stock.html",
        product=product,
        product_id=product_id
    )


@app.route("/update-status/<int:order_id>/<status>")
def update_status(order_id, status):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE orders
        SET status = ?
        WHERE order_id = ?
    """, (
        status,
        order_id
    ))

    conn.commit()
    conn.close()

    return redirect("/admin/orders")


@app.route("/admin/order-details/<int:order_id>")
def admin_order_details(order_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            p.product_name,
            oi.quantity,
            oi.price
        FROM order_items oi
        JOIN products p
            ON oi.product_id = p.product_id
        WHERE oi.order_id = ?
    """, (order_id,))

    rows = cursor.fetchall()

    items = []

    total = 0

    for row in rows:

        subtotal = row[1] * row[2]

        total += subtotal

        items.append({
            "product_name": row[0],
            "quantity": row[1],
            "price": row[2],
            "subtotal": subtotal
        })

    conn.close()

    return render_template(
        "admin_order_details.html",
        items=items,
        total=total,
        order_id=order_id
    )


@app.route("/admin/add-product",
           methods=["GET", "POST"])
def add_product():

    if "admin_id" not in session:
        return redirect("/admin-login")

    if request.method == "POST":

        product_name = request.form["product_name"]
        price = request.form["price"]
        stock = request.form["stock"]
        category = request.form["category"]

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO products
            (
                product_name,
                price,
                stock,
                category
            )
            VALUES
            (
                ?, ?, ?, ?
            )
        """, (
            product_name,
            price,
            stock,
            category
        ))

        conn.commit()
        conn.close()

        return redirect("/admin/products")

    return render_template(
        "add_product.html"
    )



@app.route("/admin/edit-product/<int:product_id>",
methods=["GET", "POST"])
def edit_product(product_id):

    if "admin_id" not in session:
        return redirect("/admin-login")

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":

        product_name = request.form["product_name"]
        price = request.form["price"]
        category = request.form["category"]

        cursor.execute("""
            UPDATE products
            SET product_name = ?,
                price = ?,
                category = ?
            WHERE product_id = ?
        """, (
            product_name,
            price,
            category,
            product_id
        ))

        conn.commit()
        conn.close()

        return redirect("/admin/products")

    cursor.execute("""
        SELECT
            product_name,
            price,
            stock,
            category
        FROM products
        WHERE product_id = ?
    """, (product_id,))

    product = cursor.fetchone()

    conn.close()

    return render_template(
        "edit_product.html",
        product=product,
        product_id=product_id
    )


@app.route("/admin/collected-orders")
def collected_orders():

    if "admin_id" not in session:
        return redirect("/admin-login")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            o.order_id,
            u.name,
            o.total_amount,
            o.order_date
        FROM orders o
        JOIN users u
            ON o.user_id = u.user_id
        WHERE o.status = 'Collected'
        ORDER BY o.order_date DESC
    """)

    rows = cursor.fetchall()

    orders = []

    for row in rows:

        orders.append({
            "order_id": row[0],
            "customer_name": row[1],
            "total_amount": row[2],
            "order_date": row[3]
        })

    conn.close()

    return render_template(
        "collected_orders.html",
        orders=orders
    )


@app.route("/admin/earnings", methods=["GET", "POST"])
def admin_earnings():

    if "admin_id" not in session:
        return redirect("/admin-login")

    conn = get_connection()
    cursor = conn.cursor()

    # Today's Earnings

    cursor.execute("""
        SELECT ISNULL(SUM(total_amount), 0)
        FROM orders
        WHERE status = 'Collected'
        AND CAST(order_date AS DATE) =
            CAST(GETDATE() AS DATE)
    """)

    today_earnings = cursor.fetchone()[0]

    # Lifetime Earnings

    cursor.execute("""
        SELECT ISNULL(SUM(total_amount), 0)
        FROM orders
        WHERE status = 'Collected'
    """)

    lifetime_earnings = cursor.fetchone()[0]

    selected_date = None
    date_earnings = 0
    date_orders = []

    if request.method == "POST":

        selected_date = request.form["selected_date"]

        cursor.execute("""
            SELECT ISNULL(SUM(total_amount), 0)
            FROM orders
            WHERE status = 'Collected'
            AND CAST(order_date AS DATE) = ?
        """, (selected_date,))

        date_earnings = cursor.fetchone()[0]

        cursor.execute("""
            SELECT
                o.order_id,
                u.name,
                o.total_amount
            FROM orders o
            JOIN users u
                ON o.user_id = u.user_id
            WHERE o.status = 'Collected'
            AND CAST(o.order_date AS DATE) = ?
            ORDER BY o.order_id DESC
        """, (selected_date,))

        date_orders = cursor.fetchall()

    conn.close()

    return render_template(
        "earnings.html",
        today_earnings=today_earnings,
        lifetime_earnings=lifetime_earnings,
        date_earnings=date_earnings,
        selected_date=selected_date,
        date_orders=date_orders
    )


@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("/login")
    user_id = session["user_id"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            u.name,
            u.mobile,
            u.role,
            u.status,
            b.boat_number
        FROM users u
        JOIN boats b
            ON u.boat_id = b.boat_id
        WHERE u.user_id = ?
    """, (user_id,))

    row = cursor.fetchone()

    conn.close()

    user = {
        "name": row[0],
        "mobile": row[1],
        "role": row[2],
        "status": row[3],
        "boat_number": row[4]
    }

    return render_template(
        "profile.html",
        user=user
    )


@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


@app.route("/change-password", methods=["GET", "POST"])
def change_password():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        current_password = request.form["current_password"]
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        if new_password != confirm_password:
            return render_template(
    "passwords_not_match.html"
)

        user_id = session["user_id"]

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT password
            FROM users
            WHERE user_id = ?
        """, (user_id,))

        user = cursor.fetchone()

        if user[0] != current_password:
            conn.close()
            return render_template(
    "wrong_current_password.html"
)

        cursor.execute("""
            UPDATE users
            SET password = ?
            WHERE user_id = ?
        """, (new_password, user_id))

        conn.commit()
        conn.close()

        return render_template(
    "password_changed.html"
)

    return render_template("change_password.html")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":

        mobile = request.form["mobile"]
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        if new_password != confirm_password:
            return render_template(
    "forgot_password_mismatch.html"
)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id
            FROM users
            WHERE mobile = ?
        """, (mobile,))

        user = cursor.fetchone()

        if not user:
            conn.close()
            return render_template(
    "mobile_not_found.html"
)

        cursor.execute("""
            UPDATE users
            SET password = ?
            WHERE mobile = ?
        """, (new_password, mobile))

        conn.commit()
        conn.close()

        return render_template(
    "forgot_password_success.html"
)

    return render_template("forgot_password.html")


print("BOATMART STARTED")

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )