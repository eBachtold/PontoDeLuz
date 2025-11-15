from flask import Flask, render_template, request, redirect, url_for
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

app = Flask(__name__)

# Conexão com Supabase
DATABASE_URL = os.getenv("DATABASE_URL")
print("DEBUG DATABASE_URL =", repr(DATABASE_URL))  # <-- linha nova

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não definida nas variáveis de ambiente!")

engine = create_engine(DATABASE_URL)



@app.route("/")
def home():
    return render_template("home.html")



# ------------------------
# PRODUTOS
# ------------------------

@app.route("/produtos")
def produtos():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM produtos ORDER BY id"))
        produtos = result.fetchall()
    return render_template("produtos.html", produtos=produtos)


@app.route("/produtos/novo", methods=["GET", "POST"])
def novo_produto():
    if request.method == "POST":
        codigo = request.form["codigo"]
        nome = request.form["nome"]
        categoria = request.form["categoria"]
        preco_custo = request.form["preco_custo"]
        preco_venda = request.form["preco_venda"]
        estoque = request.form["estoque"]
        observacoes = request.form["observacoes"]

        sql = text("""
            INSERT INTO produtos (codigo, nome, categoria, preco_custo, preco_venda, estoque_atual, observacoes)
            VALUES (:codigo, :nome, :categoria, :preco_custo, :preco_venda, :estoque, :observacoes)
        """)

        with engine.connect() as conn:
            conn.execute(sql, {
                "codigo": codigo,
                "nome": nome,
                "categoria": categoria,
                "preco_custo": preco_custo,
                "preco_venda": preco_venda,
                "estoque": estoque,
                "observacoes": observacoes
            })
            conn.commit()

        return redirect(url_for("produtos"))

    return render_template("novo_produto.html")


# ------------------------
# VENDAS
# ------------------------

@app.route("/vendas", methods=["GET", "POST"])
def nova_venda():
    with engine.connect() as conn:
        produtos = conn.execute(
            text("SELECT * FROM produtos ORDER BY nome")
        ).fetchall()

    if request.method == "POST":
        cliente = request.form["cliente"]
        canal = request.form["canal"]

        comissao_str = request.form.get("comissao", "").strip()
        comissao = Decimal(comissao_str.replace(",", ".")) if comissao_str else Decimal("0")

        produto_id = int(request.form["produto_id"])
        quantidade = int(request.form["quantidade"])

        with engine.connect() as conn:
            preco_row = conn.execute(
                text("SELECT preco_venda FROM produtos WHERE id = :id"),
                {"id": produto_id}
            ).fetchone()

            if not preco_row or preco_row[0] is None:
                # aqui você pode tratar melhor se quiser
                return redirect(url_for("nova_venda"))

            preco = Decimal(str(preco_row[0]))

            total = preco * quantidade
            valor_liquido = total - comissao

            venda_sql = text("""
                INSERT INTO vendas (cliente_nome, canal, total_venda, comissao_marketplace, valor_liquido)
                VALUES (:cliente, :canal, :total, :comissao, :valor_liquido)
                RETURNING id
            """)

            venda_id = conn.execute(venda_sql, {
                "cliente": cliente,
                "canal": canal,
                "total": total,
                "comissao": comissao,
                "valor_liquido": valor_liquido
            }).fetchone()[0]

            item_sql = text("""
                INSERT INTO itens_venda (venda_id, produto_id, quantidade, preco_unitario)
                VALUES (:venda, :produto, :qtd, :preco)
            """)

            conn.execute(item_sql, {
                "venda": venda_id,
                "produto": produto_id,
                "qtd": quantidade,
                "preco": preco
            })

            conn.execute(text("""
                UPDATE produtos
                SET estoque_atual = estoque_atual - :qtd
                WHERE id = :id
            """), {"qtd": quantidade, "id": produto_id})

            conn.commit()

        return redirect(url_for("home"))

    return render_template("nova_venda.html", produtos=produtos)


# ------------------------
# RELATÓRIOS
# ------------------------

@app.route("/relatorio", methods=["GET", "POST"])
def relatorio():
    vendas = None
    if request.method == "POST":
        data_inicio = request.form["inicio"]
        data_fim = request.form["fim"]

        sql = text("""
            SELECT data_venda, canal, total_venda, comissao_marketplace, valor_liquido
            FROM vendas
            WHERE data_venda BETWEEN :inicio AND :fim
            ORDER BY data_venda
        """)

        with engine.connect() as conn:
            vendas = conn.execute(sql, {
                "inicio": data_inicio,
                "fim": data_fim
            }).fetchall()

    return render_template("relatorio.html", vendas=vendas)


# ------------------------
# Rodar localmente
# ------------------------
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)