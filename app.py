from flask import Flask, render_template, redirect
from db import get_connection

app = Flask(__name__)

@app.route("/add-to-cart/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):

    user_id = 1

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

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            product_id,
            product_name,
            category,
            price,
            stock
        FROM products
    """)

    rows = cursor.fetchall()

    products = []

    for row in rows:
        products.append({
            "product_id": row[0],
            "product_name": row[1],
            "category": row[2],
            "price": row[3],
            "stock": row[4]
        })

    conn.close()

    return render_template(
        "products.html",
        products=products
    )



@app.route("/cart")
def cart():

    user_id = 1

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

    user_id = 1
    boat_id = 1

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

        product_id = item[0]
        price = item[1]
        quantity = item[2]

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

    for item in cart_items:

        product_id = item.product_id
        price = item.price
        quantity = item.quantity

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
            product_id,
            quantity,
            price
        ))

        cursor.execute("""
            UPDATE products
            SET stock = stock - ?
            WHERE product_id = ?
        """, (
            quantity,
            product_id
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

    user_id = 1

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







if __name__ == "__main__":
    app.run(debug=True)