from flask import Flask, render_template, request, redirect, url_for
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
from decimal import Decimal
from flask import flash, redirect, url_for, render_template, request

load_dotenv()


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallback-chave-local") #Chave para usar na rede
#app.secret_key = "chave-muito-secreta-e-grande-123"  # chave para usar localmente para testes

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
    codigo = request.args.get("codigo", "").strip()
    categoria = request.args.get("categoria", "").strip()

    query = "SELECT * FROM produtos"
    conditions = []
    params = {}

    if codigo:
        conditions.append("UPPER(codigo) LIKE UPPER(:codigo)")
        params["codigo"] = f"%{codigo}%"

    if categoria:
        conditions.append("UPPER(categoria) LIKE UPPER(:categoria)")
        params["categoria"] = f"%{categoria}%"

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY id"

    with engine.connect() as conn:
        result = conn.execute(text(query), params)
        produtos = result.fetchall()

    return render_template(
        "produtos.html",
        produtos=produtos,
        filtro_codigo=codigo,
        filtro_categoria=categoria,
    )

@app.route("/produtos/novo", methods=["GET", "POST"])
def novo_produto():
    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        nome = request.form.get("nome", "").strip()
        categoria = request.form.get("categoria", "").strip()
        preco_custo = request.form.get("preco_custo", "0").replace(",", ".")
        preco_venda = request.form.get("preco_venda", "0").replace(",", ".")
        estoque = request.form.get("estoque", "0")
        observacoes = request.form.get("observacoes", "").strip()

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

    # GET SEMPRE cai aqui:
    return render_template("novo_produto.html")

# ------------------------
# PRODUTOS EDIÇÃO
# ------------------------

@app.route("/produtos/<int:produto_id>/editar", methods=["GET", "POST"])
def editar_produto(produto_id):
    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        nome = request.form.get("nome", "").strip()
        categoria = request.form.get("categoria", "").strip()
        preco_custo = request.form.get("preco_custo", "0").replace(",", ".")
        preco_venda = request.form.get("preco_venda", "0").replace(",", ".")
        estoque = request.form.get("estoque", "0")
        observacoes = request.form.get("observacoes", "").strip()

        sql = text("""
            UPDATE produtos
            SET codigo = :codigo,
                nome = :nome,
                categoria = :categoria,
                preco_custo = :preco_custo,
                preco_venda = :preco_venda,
                estoque_atual = :estoque,
                observacoes = :observacoes
            WHERE id = :id
        """)

        with engine.connect() as conn:
            conn.execute(sql, {
                "codigo": codigo,
                "nome": nome,
                "categoria": categoria,
                "preco_custo": preco_custo,
                "preco_venda": preco_venda,
                "estoque": estoque,
                "observacoes": observacoes,
                "id": produto_id
            })
            conn.commit()

        flash("Produto atualizado com sucesso!", "success")
        return redirect(url_for("produtos"))

    # GET: buscar dados do produto para preencher o formulário
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM produtos WHERE id = :id"),
            {"id": produto_id}
        ).fetchone()

    if not row:
        flash("Produto não encontrado.", "danger")
        return redirect(url_for("produtos"))

    return render_template("editar_produto.html", produto=row)

from sqlalchemy.exc import IntegrityError

# ------------------------
# EXCLUIR PRODUTO
# ------------------------

@app.route("/produtos/<int:produto_id>/excluir", methods=["POST"])
def excluir_produto(produto_id):
    try:
        with engine.connect() as conn:
            conn.execute(
                text("DELETE FROM produtos WHERE id = :id"),
                {"id": produto_id}
            )
            conn.commit()

        flash("Produto excluído com sucesso!", "success")
    except IntegrityError:
        # Se o produto estiver vinculado a vendas, por exemplo
        flash("Não foi possível excluir: produto vinculado a vendas.", "danger")

    return redirect(url_for("produtos"))


# ------------------------
# BUSCA DE PRODUTOS PARA VENDAS
# ------------------------

@app.route("/api/produto/<codigo>")
def api_get_produto(codigo):
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT id, nome, preco_venda, estoque_atual
                FROM produtos
                WHERE TRIM(UPPER(codigo)) = TRIM(UPPER(:codigo))
            """),
            {"codigo": codigo}
        ).fetchone()

    if not row:
        return {"status": "not_found"}

    return {
        "status": "ok",
        "id": row[0],
        "nome": row[1],
        "preco": float(row[2]),
        "estoque": row[3]
    }


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

        # 🆕 campo de busca por referência
        produto_codigo = request.form.get("produto_codigo", "").strip()

        with engine.connect() as conn:
            if produto_codigo:
                # Busca pelo código (referência)
                produto_row = conn.execute(
                    text("SELECT id, preco_venda, nome FROM produtos WHERE codigo = :codigo"),
                    {"codigo": produto_codigo}
                ).fetchone()

                if not produto_row:
                    flash("Produto não encontrado para a referência informada.", "danger")
                    return redirect(url_for("nova_venda"))

                produto_id = produto_row[0]
                preco = Decimal(str(produto_row[1]))
            else:
                # Continua aceitando o select normal
                produto_id = int(request.form["produto_id"])
                produto_row = conn.execute(
                    text("SELECT preco_venda FROM produtos WHERE id = :id"),
                    {"id": produto_id}
                ).fetchone()

                if not produto_row or produto_row[0] is None:
                    flash("Produto inválido.", "danger")
                    return redirect(url_for("nova_venda"))

                preco = Decimal(str(produto_row[0]))

            quantidade = int(request.form["quantidade"])

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

        flash("Venda registrada com sucesso!", "success")
        return redirect(url_for("nova_venda"))

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