import os
import sqlite3
import psycopg2
import psycopg2.extras
from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify
import json
from datetime import datetime
import urllib.parse
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_super_segura'

# Pega a URL do Neon automaticamente pelo ambiente do Cloud Run
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    if DATABASE_URL:
        # Conecta no PostgreSQL do Neon usando a URL com pooler
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        return conn
    else:
        # Usa o SQLite local quando rodar na sua máquina
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if DATABASE_URL:
        # Estrutura para PostgreSQL (Neon)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ordens_servico (
            id SERIAL PRIMARY KEY,
            cliente TEXT,
            cpf_cnpj TEXT,
            contato TEXT,
            email_end TEXT,
            tipo_equip TEXT,
            marca TEXT,
            equipamento TEXT,
            ns_patrimonio TEXT,
            acessorios TEXT,
            condicao TEXT,
            status TEXT,
            defeito TEXT,
            diagnostico TEXT,
            servico TEXT,
            servicos_json TEXT,
            peca_utilizada TEXT,
            pecas_json TEXT,
            valor_pecas REAL,
            valor_servico REAL,
            valor REAL,
            data_abertura TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ordem_entrada (
            id SERIAL PRIMARY KEY,
            cliente TEXT,
            cpf_cnpj TEXT,
            contato TEXT,
            email TEXT,
            tipo_equip TEXT,
            marca TEXT,
            equipamento TEXT,
            ns_patrimonio TEXT,
            acessorios TEXT,
            condicao TEXT,
            defeito TEXT,
            data_entrada TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id SERIAL PRIMARY KEY,
            nome TEXT,
            cpf_cnpj TEXT,
            contato TEXT,
            email TEXT,
            cep TEXT,
            rua TEXT,
            numero TEXT,
            bairro TEXT,
            complemento TEXT,
            cidade_uf TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS servicos_cadastrados (
            id SERIAL PRIMARY KEY,
            nome_servico TEXT,
            descricao TEXT,
            valor_padrao REAL
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS pecas_estoque (
            id SERIAL PRIMARY KEY,
            nome_peca TEXT,
            codigo TEXT,
            quantidade INTEGER,
            valor_custo REAL,
            valor_venda REAL
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS boletos (
            id SERIAL PRIMARY KEY,
            cliente TEXT,
            numero_documento TEXT,
            valor REAL,
            data_vencimento TEXT,
            data_pagamento TEXT,
            status TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS notas_fiscais (
            id SERIAL PRIMARY KEY,
            numero_nf TEXT,
            cliente TEXT,
            valor REAL,
            data_emissao TEXT,
            status TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS despesas (
            id SERIAL PRIMARY KEY,
            descricao TEXT,
            categoria TEXT,
            valor REAL,
            data_despesa TEXT
        )
        ''')
    else:
        # Estrutura original para SQLite (Local)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ordens_servico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT,
            cpf_cnpj TEXT,
            contato TEXT,
            email_end TEXT,
            tipo_equip TEXT,
            marca TEXT,
            equipamento TEXT,
            ns_patrimonio TEXT,
            acessorios TEXT,
            condicao TEXT,
            status TEXT,
            defeito TEXT,
            diagnostico TEXT,
            servico TEXT,
            servicos_json TEXT,
            peca_utilizada TEXT,
            pecas_json TEXT,
            valor_pecas REAL,
            valor_servico REAL,
            valor REAL,
            data_abertura TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ordem_entrada (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT,
            cpf_cnpj TEXT,
            contato TEXT,
            email TEXT,
            tipo_equip TEXT,
            marca TEXT,
            equipamento TEXT,
            ns_patrimonio TEXT,
            acessorios TEXT,
            condicao TEXT,
            defeito TEXT,
            data_entrada TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            cpf_cnpj TEXT,
            contato TEXT,
            email TEXT,
            cep TEXT,
            rua TEXT,
            numero TEXT,
            bairro TEXT,
            complemento TEXT,
            cidade_uf TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS servicos_cadastrados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_servico TEXT,
            descricao TEXT,
            valor_padrao REAL
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS pecas_estoque (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_peca TEXT,
            codigo TEXT,
            quantidade INTEGER,
            valor_custo REAL,
            valor_venda REAL
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS boletos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT,
            numero_documento TEXT,
            valor REAL,
            data_vencimento TEXT,
            data_pagamento TEXT,
            status TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS notas_fiscais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_nf TEXT,
            cliente TEXT,
            valor REAL,
            data_emissao TEXT,
            status TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS despesas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT,
            categoria TEXT,
            valor REAL,
            data_despesa TEXT
        )
        ''')

    conn.commit()
    conn.close()

init_db()

EMAIL_REMETENTE = "seu_email@gmail.com"
EMAIL_SENHA = "sua_senha_de_app"

def enviar_email_com_anexo_smtp(destinatario, assunto, corpo_html, pdf_bytes, nome_pdf):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_REMETENTE
        msg['To'] = destinatario
        msg['Subject'] = assunto

        msg.attach(MIMEText(corpo_html, 'html'))

        parte_anexo = MIMEBase('application', 'octet-stream')
        parte_anexo.set_payload(pdf_bytes)
        encoders.encode_base64(parte_anexo)
        parte_anexo.add_header('Content-Disposition', f'attachment; filename="{nome_pdf}"')
        msg.attach(parte_anexo)

        servidor = smtplib.SMTP('smtp.gmail.com', 587)
        servidor.starttls()
        servidor.login(EMAIL_REMETENTE, EMAIL_SENHA)
        servidor.sendmail(EMAIL_REMETENTE, destinatario, msg.as_string())
        servidor.quit()
        return True, "E-mail enviado com sucesso!"
    except Exception as e:
        return False, str(e)

BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Clínica do Hardware - Sistema de Gestão</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background-color: #f8f9fa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .sidebar { min-height: 100vh; background-color: #002060; color: #fff; position: fixed; top: 0; left: 0; width: 250px; z-index: 1000; box-shadow: 3px 0 10px rgba(0,0,0,0.1); }
        .sidebar .brand { font-size: 1.2rem; font-weight: bold; padding: 20px; background-color: #00153f; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.1); }
        .sidebar .nav-link { color: rgba(255,255,255,0.8); padding: 12px 20px; font-weight: 500; transition: all 0.3s; }
        .sidebar .nav-link:hover, .sidebar .nav-link.active { background-color: #003399; color: #fff; border-left: 4px solid #ffc107; }
        .sidebar .nav-link i { margin-right: 10px; width: 20px; text-align: center; }
        .main-content { margin-left: 250px; padding: 30px; }
        .header-custom { background: #fff; padding: 20px 30px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 30px; }
        .card { border: none; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    </style>
</head>
<body>
    <div class="sidebar d-flex flex-column">
        <div class="brand"><i class="fas fa-laptop-medical"></i> CLÍNICA DO HARDWARE</div>
        <ul class="nav flex-column flex-grow-1 py-3">
            <li class="nav-item"><a href="/" class="nav-link {% if active_tab == 'os' %}active{% endif %}"><i class="fas fa-clipboard-list"></i> Ordens de Serviço</a></li>
            <li class="nav-item"><a href="/entrada" class="nav-link {% if active_tab == 'entrada' %}active{% endif %}"><i class="fas fa-sign-in-alt"></i> Entrada na Recepção</a></li>
            <li class="nav-item"><a href="/clientes" class="nav-link {% if active_tab == 'clientes' %}active{% endif %}"><i class="fas fa-users"></i> Clientes</a></li>
            <li class="nav-item"><a href="/servicos" class="nav-link {% if active_tab == 'servicos' %}active{% endif %}"><i class="fas fa-tools"></i> Serviços</a></li>
            <li class="nav-item"><a href="/pecas" class="nav-link {% if active_tab == 'pecas' %}active{% endif %}"><i class="fas fa-boxes"></i> Peças / Estoque</a></li>
            <li class="nav-item"><a href="/boletos" class="nav-link {% if active_tab == 'boletos' %}active{% endif %}"><i class="fas fa-credit-card"></i> Boletos</a></li>
            <li class="nav-item"><a href="/nfs" class="nav-link {% if active_tab == 'nfs' %}active{% endif %}"><i class="fas fa-receipt"></i> Notas Fiscais</a></li>
            <li class="nav-item"><a href="/despesas" class="nav-link {% if active_tab == 'despesas' %}active{% endif %}"><i class="fas fa-chart-line"></i> Despesas</a></li>
            <li class="nav-item"><a href="/financeiro" class="nav-link {% if active_tab == 'financeiro' %}active{% endif %}"><i class="fas fa-chart-pie"></i> Painel Financeiro</a></li>
        </ul>
    </div>
    <div class="main-content">
        <div class="container-fluid">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ 'success' if category == 'success' else 'danger' }} alert-dismissible fade show" role="alert">
                            {{ message }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
            {% block content %}{% endblock %}
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let servicosDisponiveis = [];
        let pecasDisponiveis = [];

        function inicializarServicosDisponiveis(lista) { servicosDisponiveis = lista; }
        function inicializarPecasDisponiveis(lista) { pecasDisponiveis = lista; }

        function adicionarLinhaServico(nomeSelecionado = '', quantidadeVal = 1, valorUnitVal = 0) {
            let container = document.getElementById('container-servicos');
            let optionsHtml = '<option value="">-- Selecione o Serviço --</option>';
            servicosDisponiveis.forEach(s => {
                let sel = (s.nome_servico === nomeSelecionado) ? 'selected' : '';
                optionsHtml += `<option value="${s.nome_servico}" data-valor="${s.valor_padrao}" ${sel}>${s.nome_servico} (R$ ${s.valor_padrao.toFixed(2)})</option>`;
            });

            let row = document.createElement('div');
            row.className = 'row g-2 mb-2 align-items-center linha-servico';
            row.innerHTML = `
                <div class="col-md-6">
                    <select class="form-select form-select-sm select-servico" onchange="atualizarValorServico(this)">
                        ${optionsHtml}
                    </select>
                </div>
                <div class="col-md-2">
                    <input type="number" class="form-control form-control-sm qtd-servico" value="${quantidadeVal}" min="1" placeholder="Qtd" oninput="recalcularTotais()">
                </div>
                <div class="col-md-3">
                    <input type="number" step="0.01" class="form-control form-control-sm valor-servico" value="${valorUnitVal}" placeholder="Valor Unit. R$" oninput="recalcularTotais()">
                </div>
                <div class="col-md-1 text-end">
                    <button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('.linha-servico').remove(); recalcularTotais();"><i class="fas fa-trash"></i></button>
                </div>
            `;
            container.appendChild(row);
            if(nomeSelecionado && valorUnitVal === 0) {
                let select = row.querySelector('.select-servico');
                atualizarValorServico(select);
            }
            recalcularTotais();
        }

        function atualizarValorServico(selectElem) {
            let selectedOption = selectElem.options[selectElem.selectedIndex];
            let valorPadrao = selectedOption.getAttribute('data-valor') || 0;
            let row = selectElem.closest('.linha-servico');
            let inputValor = row.querySelector('.valor-servico');
            inputValor.value = parseFloat(valorPadrao).toFixed(2);
            recalcularTotais();
        }

        function adicionarLinhaPeca(nomeSelecionado = '', quantidadeVal = 1, valorUnitVal = 0) {
            let container = document.getElementById('container-pecas');
            let optionsHtml = '<option value="">-- Selecione a Peça do Estoque --</option>';
            pecasDisponiveis.forEach(p => {
                let sel = (p.nome_peca === nomeSelecionado) ? 'selected' : '';
                optionsHtml += `<option value="${p.nome_peca}" data-valor="${p.valor_venda}" data-estoque="${p.quantidade}" ${sel}>${p.nome_peca} (Estoque: ${p.quantidade} | R$ ${p.valor_venda.toFixed(2)})</option>`;
            });

            let row = document.createElement('div');
            row.className = 'row g-2 mb-2 align-items-center linha-peca';
            row.innerHTML = `
                <div class="col-md-6">
                    <select class="form-select form-select-sm select-peca" onchange="atualizarValorPeca(this)">
                        ${optionsHtml}
                    </select>
                </div>
                <div class="col-md-2">
                    <input type="number" class="form-control form-control-sm qtd-peca" value="${quantidadeVal}" min="1" placeholder="Qtd" oninput="recalcularTotais()">
                </div>
                <div class="col-md-3">
                    <input type="number" step="0.01" class="form-control form-control-sm valor-peca" value="${valorUnitVal}" placeholder="Valor Unit. R$" oninput="recalcularTotais()">
                </div>
                <div class="col-md-1 text-end">
                    <button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('.linha-peca').remove(); recalcularTotais();"><i class="fas fa-trash"></i></button>
                </div>
            `;
            container.appendChild(row);
            if(nomeSelecionado && valorUnitVal === 0) {
                let select = row.querySelector('.select-peca');
                atualizarValorPeca(select);
            }
            recalcularTotais();
        }

        function atualizarValorPeca(selectElem) {
            let selectedOption = selectElem.options[selectElem.selectedIndex];
            let valorVenda = selectedOption.getAttribute('data-valor') || 0;
            let row = selectElem.closest('.linha-peca');
            let inputValor = row.querySelector('.valor-peca');
            inputValor.value = parseFloat(valorVenda).toFixed(2);
            recalcularTotais();
        }

        function recalcularTotais() {
            let totalServicos = 0;
            let servicosArray = [];
            document.querySelectorAll('.linha-servico').forEach(row => {
                let nome = row.querySelector('.select-servico').value;
                let qtd = parseFloat(row.querySelector('.qtd-servico').value) || 0;
                let valor = parseFloat(row.querySelector('.valor-servico').value) || 0;
                if(nome) {
                    totalServicos += qtd * valor;
                    servicosArray.push({nome: nome, quantidade: qtd, valor_unitario: valor});
                }
            });

            let totalPecas = 0;
            let pecasArray = [];
            document.querySelectorAll('.linha-peca').forEach(row => {
                let nome = row.querySelector('.select-peca').value;
                let qtd = parseFloat(row.querySelector('.qtd-peca').value) || 0;
                let valor = parseFloat(row.querySelector('.valor-peca').value) || 0;
                if(nome) {
                    totalPecas += qtd * valor;
                    pecasArray.push({nome: nome, quantidade: qtd, valor_unitario: valor});
                }
            });

            document.getElementById('valor_servico_input').value = totalServicos.toFixed(2);
            document.getElementById('valor_pecas_input').value = totalPecas.toFixed(2);
            let totalGeral = totalServicos + totalPecas;
            document.getElementById('valor_total_input').value = "R$ " + totalGeral.toFixed(2);

            document.getElementById('servicos_json_input').value = JSON.stringify(servicosArray);
            document.getElementById('pecas_json_input').value = JSON.stringify(pecasArray);
        }

        function consultarCnpjCompleto(idCnpj, idNome, idContato, idEmail, idCep = null, idRua = null, idNum = null, idBairro = null, idCompl = null, idCidade = null) {
            let cnpjInput = document.getElementById(idCnpj);
            if(!cnpjInput) return;
            let cnpj = cnpjInput.value.replace(/\\D/g, '');
            if(cnpj.length !== 14) return;

            fetch(`https://brasilapi.com.br/api/cnpj/v1/${cnpj}`)
                .then(response => response.json())
                .then(data => {
                    if(!data.erro) {
                        if(idNome) document.getElementById(idNome).value = data.razao_social || data.nome_fantasia || '';
                        if(idContato) document.getElementById(idContato).value = data.ddd_telefone_1 || '';
                        if(idEmail) document.getElementById(idEmail).value = data.email || '';
                        if(idCep && data.cep) document.getElementById(idCep).value = data.cep;
                        if(idRua && data.logradouro) document.getElementById(idRua).value = data.logradouro;
                        if(idNum && data.numero) document.getElementById(idNum).value = data.numero;
                        if(idBairro && data.bairro) document.getElementById(idBairro).value = data.bairro;
                        if(idCompl && data.complemento) document.getElementById(idCompl).value = data.complemento;
                        if(idCidade && data.municipio) document.getElementById(idCidade).value = data.municipio + ' / ' + (data.uf || '');
                    }
                })
                .catch(err => console.error('Erro ao consultar CNPJ:', err));
        }

        function consultarCep(idCep, idRua, idBairro, idCidade) {
            let cepInput = document.getElementById(idCep);
            if(!cepInput) return;
            let cep = cepInput.value.replace(/\\D/g, '');
            if(cep.length !== 8) return;

            fetch(`https://brasilapi.com.br/api/cep/v2/${cep}`)
                .then(response => response.json())
                .then(data => {
                    if(!data.erro) {
                        if(idRua) document.getElementById(idRua).value = data.street || '';
                        if(idBairro) document.getElementById(idBairro).value = data.neighborhood || '';
                        if(idCidade) document.getElementById(idCidade).value = (data.city || '') + ' / ' + (data.state || '');
                    }
                })
                .catch(err => console.error('Erro ao consultar CEP:', err));
        }

        function preencherDadosEntrada(selectElem) {
            let opt = selectElem.options[selectElem.selectedIndex];
            if(!opt.value) return;
            document.getElementById('cliente_field').value = opt.getAttribute('data-cliente') || '';
            document.getElementById('cpf_cnpj_field').value = opt.getAttribute('data-doc') || '';
            document.getElementById('contato_field').value = opt.getAttribute('data-contato') || '';
            document.getElementById('email_field').value = opt.getAttribute('data-email') || '';
            
            let tipo = document.querySelector('[name="tipo_equip"]'); if(tipo) tipo.value = opt.getAttribute('data-tipo') || '';
            let marca = document.querySelector('[name="marca"]'); if(marca) marca.value = opt.getAttribute('data-marca') || '';
            let equip = document.querySelector('[name="equipamento"]'); if(equip) equip.value = opt.getAttribute('data-equip') || '';
            let ns = document.querySelector('[name="ns_patrimonio"]'); if(ns) ns.value = opt.getAttribute('data-ns') || '';
            let acessorios = document.querySelector('[name="acessorios"]'); if(acessorios) acessorios.value = opt.getAttribute('data-acessorios') || '';
            let condicao = document.querySelector('[name="condicao"]'); if(condicao) condicao.value = opt.getAttribute('data-condicao') || '';
            let defeito = document.querySelector('[name="defeito"]'); if(defeito) defeito.value = opt.getAttribute('data-defeito') || '';
        }

        function filtrarTabela(inputId, tabelaId) {
            let input = document.getElementById(inputId);
            let filter = input.value.toLowerCase();
            let table = document.getElementById(tabelaId);
            let trs = table.getElementsByTagName('tr');

            for (let i = 1; i < trs.length; i++) {
                let tds = trs[i].getElementsByTagName('td');
                let found = false;
                for (let j = 0; j < tds.length; j++) {
                    if (tds[j]) {
                        if (tds[j].textContent.toLowerCase().indexOf(filter) > -1) {
                            found = true;
                            break;
                        }
                    }
                }
                trs[i].style.display = found ? '' : 'none';
            }
        }

        function alterarStatusRapido(id, novoStatus) {
            fetch(`/os/status_rapido/${id}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({status: novoStatus})
            })
            .then(res => res.json())
            .then(data => {
                if(data.sucesso) {
                    location.reload();
                } else {
                    alert('Erro ao atualizar status.');
                }
            });
        }
    </script>
</body>
</html>
"""

@app.route('/entrada', methods=['GET', 'POST'])
def entrada_recepcao():
    conn = get_db_connection()
    if request.method == 'POST':
        cliente = request.form['cliente']
        cpf_cnpj = request.form['cpf_cnpj']
        contato = request.form['contato']
        email = request.form['email']
        tipo_equip = request.form['tipo_equip']
        marca = request.form['marca']
        equipamento = request.form['equipamento']
        ns_patrimonio = request.form['ns_patrimonio']
        
        acessorios_lista = request.form.getlist('acessorio_chk')
        acessorios_outro = request.form.get('acessorios_outro', '').strip()
        if acessorios_outro:
            acessorios_lista.append(acessorios_outro)
        acessorios = ", ".join(acessorios_lista)

        condicao_lista = request.form.getlist('condicao_chk')
        condicao_outro = request.form.get('condicao_outro', '').strip()
        if condicao_outro:
            condicao_lista.append(condicao_outro)
        condicao = ", ".join(condicao_lista)

        defeito = request.form['defeito']
        data_hoje = datetime.now().strftime("%Y-%m-%d")

        cursor = conn.cursor()
        cursor.execute("""INSERT INTO ordem_entrada 
                        (cliente, cpf_cnpj, contato, email, tipo_equip, marca, equipamento, ns_patrimonio, acessorios, condicao, defeito, data_entrada) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""" if DATABASE_URL else
                       """INSERT INTO ordem_entrada 
                        (cliente, cpf_cnpj, contato, email, tipo_equip, marca, equipamento, ns_patrimonio, acessorios, condicao, defeito, data_entrada) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                   (cliente, cpf_cnpj, contato, email, tipo_equip, marca, equipamento, ns_patrimonio, acessorios, condicao, defeito, data_hoje))
        conn.commit()
        conn.close()
        flash("Entrada na recepção registrada com sucesso!", "success")
        return redirect(url_for('entrada_recepcao'))

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ordem_entrada ORDER BY id DESC")
    lista_entradas = cursor.fetchall()
    conn.close()

    linhas_tabela_entradas = "".join([
        f"<tr>"
        f"<td><strong>ENT-{e['id']:04d}</strong></td>"
        f"<td>{e['cliente']}</td>"
        f"<td>{e['tipo_equip']} {e['marca'] or ''} {e['equipamento']}</td>"
        f"<td>{e['defeito'] or '-'}</td>"
        f"<td>{e['data_entrada']}</td>"
        f"<td>"
        f"<a href='/os/nova_de_entrada/{e['id']}' class='btn btn-sm btn-success' title='Gerar Orçamento / O.S.'><i class='fas fa-file-invoice-dollar'></i> Gerar O.S.</a> "
        f"<a href='/entrada/excluir/{e['id']}' class='btn btn-sm btn-danger' onclick=\"return confirm('Deseja excluir este registro de entrada?');\"><i class='fas fa-trash'></i></a>"
        f"</td>"
        f"</tr>"
        for e in lista_entradas
    ]) if lista_entradas else "<tr><td colspan='6' class='text-center text-muted'>Nenhum equipamento na recepção.</td></tr>"

    html_page = BASE_TEMPLATE.replace("{% block content %}{% endblock %}", f"""
    <div class="header-custom">
        <h2><i class="fas fa-sign-in-alt"></i> Recepção / Entrada de Equipamentos</h2>
        <p class="mb-0">Registre o check-in do equipamento trazido pelo cliente.</p>
    </div>

    <div class="card p-4 mb-4">
        <h4>Novo Check-in de Recepção</h4>
        <form method="POST" class="row g-3">
            <div class="col-md-6">
                <label class="form-label">Cliente / Razão Social:</label>
                <input type="text" class="form-control" id="cliente_field" name="cliente" required>
            </div>
            <div class="col-md-6">
                <label class="form-label">CPF / CNPJ:</label>
                <input type="text" class="form-control" id="cpf_cnpj_field" name="cpf_cnpj" placeholder="Digite o CNPJ" onblur="consultarCnpjCompleto('cpf_cnpj_field', 'cliente_field', 'contato_field', 'email_field')">
            </div>
            <div class="col-md-6">
                <label class="form-label">Contato (WhatsApp):</label>
                <input type="text" class="form-control" id="contato_field" name="contato">
            </div>
            <div class="col-md-6">
                <label class="form-label">E-mail do Cliente:</label>
                <input type="email" class="form-control" id="email_field" name="email">
            </div>
            <div class="col-md-4">
                <label class="form-label">Tipo de Equipamento:</label>
                <input type="text" class="form-control" name="tipo_equip" value="NOTEBOOK" required>
            </div>
            <div class="col-md-4">
                <label class="form-label">Marca:</label>
                <input type="text" class="form-control" name="marca" placeholder="Ex: Dell">
            </div>
            <div class="col-md-4">
                <label class="form-label">Modelo:</label>
                <input type="text" class="form-control" name="equipamento" placeholder="Ex: Inspiron 15" required>
            </div>
            <div class="col-md-6">
                <label class="form-label">Nº de Série / Patrimônio:</label>
                <input type="text" class="form-control" name="ns_patrimonio">
            </div>

            <div class="col-md-6">
                <label class="form-label fw-bold">Acessórios Deixados:</label>
                <div class="p-2 border rounded bg-light mb-1">
                    <div class="form-check form-check-inline">
                        <input class="form-check-input" type="checkbox" name="acessorio_chk" value="Carregador" id="acess1">
                        <label class="form-check-label" for="acess1">Carregador</label>
                    </div>
                    <div class="form-check form-check-inline">
                        <input class="form-check-input" type="checkbox" name="acessorio_chk" value="Bateria" id="acess2">
                        <label class="form-check-label" for="acess2">Bateria</label>
                    </div>
                    <div class="form-check form-check-inline">
                        <input class="form-check-input" type="checkbox" name="acessorio_chk" value="Bolsa/Case" id="acess3">
                        <label class="form-check-label" for="acess3">Bolsa / Case</label>
                    </div>
                    <div class="form-check form-check-inline">
                        <input class="form-check-input" type="checkbox" name="acessorio_chk" value="Mouse" id="acess4">
                        <label class="form-check-label" for="acess4">Mouse</label>
                    </div>
                </div>
                <input type="text" class="form-control form-control-sm" name="acessorios_outro" placeholder="Outros acessórios (opcional)">
            </div>

            <div class="col-md-12">
                <label class="form-label fw-bold">Condição Visual do Equipamento:</label>
                <div class="p-2 border rounded bg-light mb-1">
                    <div class="form-check form-check-inline">
                        <input class="form-check-input" type="checkbox" name="condicao_chk" value="Sem arranhões" id="cond1">
                        <label class="form-check-label" for="cond1">Sem arranhões</label>
                    </div>
                    <div class="form-check form-check-inline">
                        <input class="form-check-input" type="checkbox" name="condicao_chk" value="Riscos na tampa" id="cond2">
                        <label class="form-check-label" for="cond2">Riscos na tampa</label>
                    </div>
                    <div class="form-check form-check-inline">
                        <input class="form-check-input" type="checkbox" name="condicao_chk" value="Riscos na base/teclado" id="cond3">
                        <label class="form-check-label" for="cond3">Riscos na base/teclado</label>
                    </div>
                    <div class="form-check form-check-inline">
                        <input class="form-check-input" type="checkbox" name="condicao_chk" value="Amassados" id="cond4">
                        <label class="form-check-label" for="cond4">Amassados</label>
                    </div>
                    <div class="form-check form-check-inline">
                        <input class="form-check-input" type="checkbox" name="condicao_chk" value="Parafusos faltando" id="cond5">
                        <label class="form-check-label" for="cond5">Parafusos faltando</label>
                    </div>
                    <div class="form-check form-check-inline">
                        <input class="form-check-input" type="checkbox" name="condicao_chk" value="Tela riscada/trincada" id="cond6">
                        <label class="form-check-label" for="cond6">Tela riscada/trincada</label>
                    </div>
                </div>
                <input type="text" class="form-control form-control-sm" name="condicao_outro" placeholder="Outras observações visuais (opcional)">
            </div>

            <div class="col-md-12">
                <label class="form-label">Defeito Relatado:</label>
                <textarea class="form-control" name="defeito" rows="2" placeholder="Descreva o problema relatado pelo cliente..."></textarea>
            </div>
            <div class="col-12 mt-4">
                <button type="submit" class="btn btn-primary"><i class="fas fa-save"></i> Registrar Entrada</button>
            </div>
        </form>
    </div>

    <div class="card p-3">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h4 class="mb-0">Equipamentos na Recepção (Pendentes de O.S.)</h4>
            <div style="width: 300px;">
                <input type="text" id="filtroEntrada" class="form-control form-control-sm" placeholder="🔍 Filtrar entradas..." onkeyup="filtrarTabela('filtroEntrada', 'tabelaEntrada')">
            </div>
        </div>
        <div class="table-responsive">
            <table id="tabelaEntrada" class="table table-striped align-middle">
                <thead class="table-dark">
                    <tr>
                        <th>Nº Entrada</th>
                        <th>Cliente</th>
                        <th>Equipamento</th>
                        <th>Defeito</th>
                        <th>Data</th>
                        <th>Ações</th>
                    </tr>
                </thead>
                <tbody>
                    {linhas_tabela_entradas}
                </tbody>
            </table>
        </div>
    </div>
    """)
    return render_template_string(html_page, active_tab='entrada')

@app.route('/entrada/excluir/<int:id>')
def excluir_entrada(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ordem_entrada WHERE id = %s" if DATABASE_URL else "DELETE FROM ordem_entrada WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Registro de entrada excluído com sucesso!", "success")
    return redirect(url_for('entrada_recepcao'))

@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ordens_servico ORDER BY id DESC")
    raw_os_list = cursor.fetchall()
    conn.close()
    
    os_list = []
    for row in raw_os_list:
        item = dict(row)
        item['os_formatada'] = f"OS-{item['id']:04d}"
        os_list.append(item)

    linhas_tabela_os = ""
    for r in os_list:
        contato_digitos = ''.join(filter(str.isdigit, str(r['contato'] or '')))
        whatsapp_msg = urllib.parse.quote(f"Olá *{r['cliente']}*, sua O.S. *OS-{r['id']:04d}* referente ao equipamento *{r['tipo_equip']} {r['marca'] or ''} {r['equipamento']}* encontra-se com status: *{r['status']}*. Valor total: R$ {r['valor']:.2f}. Agradecemos a preferência!")
        
        sel_aprov = 'selected' if r['status'] == 'Aguardando Aprovação' else ''
        sel_exec = 'selected' if r['status'] == 'Em Execução' else ''
        sel_executado = 'selected' if r['status'] == 'Executado' else ''

        linhas_tabela_os += f"""
        <tr>
            <td><strong>{r['os_formatada']}</strong></td>
            <td>{r['cliente']}</td>
            <td>{r['equipamento']}</td>
            <td>R$ {r['valor']:.2f}</td>
            <td>
                <select class='form-select form-select-sm fw-bold' style='width: 175px;' onchange='alterarStatusRapido({r['id']}, this.value)'>
                    <option value='Aguardando Aprovação' {sel_aprov}>Aguardando Aprovação</option>
                    <option value='Em Execução' {sel_exec}>Em Execução</option>
                    <option value='Executado' {sel_executado}>Executado</option>
                </select>
            </td>
            <td>{r['data_abertura']}</td>
            <td>
                <div class='btn-group btn-group-sm mb-1'>
                    <a href='/os/imprimir/{r['id']}' class='btn btn-primary' target='_blank' title='2 Vias (Imprimir/PDF)'><i class='fas fa-print'></i> 2 Vias</a>
                    <a href='/os/imprimir_via_unica/{r['id']}' class='btn btn-outline-primary' target='_blank' title='Via Única Cliente' style='background:#e7f1ff;'><i class='fas fa-file-alt'></i> Via Única</a>
                </div>
                <div class='btn-group btn-group-sm'>
                    <a href='/os/enviar_email/{r['id']}' class='btn btn-warning' title='Enviar por E-mail (Gmail)'><i class='fas fa-envelope'></i></a>
                    <a href='https://api.whatsapp.com/send?phone=55{contato_digitos}&text={whatsapp_msg}' target='_blank' class='btn btn-success' title='Enviar no WhatsApp'><i class='fab fa-whatsapp'></i></a>
                    <a href='/os/editar/{r['id']}' class='btn btn-secondary' title='Editar'><i class='fas fa-edit'></i></a>
                    <a href='/os/excluir/{r['id']}' class='btn btn-danger' onclick="return confirm('Deseja excluir esta O.S.?');" title='Excluir'><i class='fas fa-trash'></i></a>
                </div>
            </td>
        </tr>
        """
    if not os_list:
        linhas_tabela_os = "<tr><td colspan='7' class='text-center text-muted'>Nenhuma Ordem de Serviço cadastrada.</td></tr>"

    html_page = BASE_TEMPLATE.replace("{% block content %}{% endblock %}", f"""
    <div class="header-custom">
        <h2><i class="fas fa-clipboard-list"></i> Ordens de Serviço</h2>
        <p class="mb-0">Gerenciamento completo de O.S. e Orçamentos</p>
    </div>
    <div class="d-flex justify-content-between align-items-center mb-3">
        <div>
            <a href="/os/nova" class="btn btn-primary"><i class="fas fa-plus"></i> Nova Ordem de Serviço Direta</a>
            <a href="/entrada" class="btn btn-info text-white ms-2"><i class="fas fa-sign-in-alt"></i> Ver Entradas na Recepção</a>
        </div>
        <div style="width: 300px;">
            <input type="text" id="filtroOS" class="form-control" placeholder="🔍 Filtrar O.S...." onkeyup="filtrarTabela('filtroOS', 'tabelaOS')">
        </div>
    </div>
    <div class="card p-3">
        <div class="table-responsive">
            <table id="tabelaOS" class="table table-striped table-hover align-middle">
                <thead class="table-dark">
                    <tr>
                        <th>Nº O.S.</th>
                        <th>Cliente</th>
                        <th>Equipamento</th>
                        <th>Valor Total</th>
                        <th>Status (Clique para Alterar)</th>
                        <th>Data</th>
                        <th>Ações / Envio</th>
                    </tr>
                </thead>
                <tbody>
                    {linhas_tabela_os}
                </tbody>
            </table>
        </div>
    </div>
    """)
    return render_template_string(html_page, active_tab='os', os_list=os_list)

@app.route('/os/imprimir/<int:id>')
def imprimir_os(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ordens_servico WHERE id = %s" if DATABASE_URL else "SELECT * FROM ordens_servico WHERE id = ?", (id,))
    os_item = cursor.fetchone()
    conn.close()
    if not os_item:
        flash("Ordem de Serviço não encontrada.", "danger")
        return redirect(url_for('index'))
    
    data_formatada = datetime.strptime(os_item['data_abertura'], "%Y-%m-%d").strftime("%d/%m/%Y") if os_item['data_abertura'] else ""

    itens_linhas_html = ""
    try:
        servicos_arr = json.loads(os_item['servicos_json']) if os_item['servicos_json'] else []
    except:
        servicos_arr = []

    if servicos_arr:
        for s in servicos_arr:
            subtotal = s['quantidade'] * s['valor_unitario']
            itens_linhas_html += f"<tr><td>Serviço</td><td>{s['nome']}</td><td class='text-center'>{s['quantidade']}</td><td class='text-end'>R$ {subtotal:.2f}</td></tr>"
    elif os_item['servico']:
        itens_linhas_html += f"<tr><td>Serviço</td><td>{os_item['servico']}</td><td class='text-center'>1</td><td class='text-end'>R$ {(os_item['valor_servico'] or 0.0):.2f}</td></tr>"

    try:
        pecas_arr = json.loads(os_item['pecas_json']) if os_item['pecas_json'] else []
    except:
        pecas_arr = []

    if pecas_arr:
        for p in pecas_arr:
            subtotal = p['quantidade'] * p['valor_unitario']
            itens_linhas_html += f"<tr><td>Peça</td><td>{p['nome']}</td><td class='text-center'>{p['quantidade']}</td><td class='text-end'>R$ {subtotal:.2f}</td></tr>"
    elif os_item['peca_utilizada']:
        itens_linhas_html += f"<tr><td>Peça</td><td>{os_item['peca_utilizada']}</td><td class='text-center'>1</td><td class='text-end'>R$ {(os_item['valor_pecas'] or 0.0):.2f}</td></tr>"

    def gerar_via_os(tipo_via):
        return f"""
        <div class="via-box">
            <div class="row header-print align-items-center">
                <div class="col-8 d-flex align-items-center">
                    <img src="/static/logo.png" alt="Logo" class="logo-img me-2" onerror="this.style.display='none'">
                    <div>
                        <h3 class="mb-1" style="font-weight: 900; color: #002060; font-size: 14px;">CLÍNICA DO HARDWARE</h3>
                        <p class="mb-0 small text-muted" style="font-size: 9px;"><strong>CNPJ:</strong> 70.017.290/0001-61 | <strong>Tel:</strong> (98) 9 8482-9705</p>
                    </div>
                </div>
                <div class="col-4 text-end">
                    <span class="badge bg-secondary mb-1" style="font-size: 9px;">{tipo_via}</span>
                    <h5 class="text-danger mb-0" style="font-weight: bold; font-size: 11px;">ORDEM DE SERVIÇO</h5>
                    <h5 class="mb-0" style="color: #002060; font-size: 12px;"><strong>Nº OS-{os_item['id']:04d}</strong></h5>
                    <small class="text-muted" style="font-size: 9px;">Data: {data_formatada} | Status: <strong>{os_item['status']}</strong></small>
                </div>
            </div>

            <div class="section-title">01 DADOS DO CLIENTE</div>
            <div class="row mb-1">
                <div class="col-8"><p class="mb-1"><strong>Cliente:</strong> {os_item['cliente']}</p></div>
                <div class="col-4"><p class="mb-1"><strong>CPF/CNPJ:</strong> {os_item['cpf_cnpj'] or 'Não informado'}</p></div>
                <div class="col-6"><p class="mb-1"><strong>Contato:</strong> {os_item['contato'] or 'Não informado'}</p></div>
                <div class="col-6"><p class="mb-1"><strong>E-mail/End:</strong> {os_item['email_end'] or 'Não informado'}</p></div>
            </div>

            <div class="section-title">02 EQUIPAMENTO & AVALIAÇÃO TÉCNICA</div>
            <div class="row mb-1">
                <div class="col-4"><p class="mb-1"><strong>Tipo:</strong> {os_item['tipo_equip']}</p></div>
                <div class="col-4"><p class="mb-1"><strong>Marca:</strong> {os_item['marca'] or '-'}</p></div>
                <div class="col-4"><p class="mb-1"><strong>Modelo:</strong> {os_item['equipamento']}</p></div>
                <div class="col-6"><p class="mb-1"><strong>Nº Série:</strong> {os_item['ns_patrimonio'] or '-'}</p></div>
                <div class="col-6"><p class="mb-1"><strong>Acessórios:</strong> {os_item['acessorios'] or 'Nenhum'}</p></div>
                <div class="col-12"><p class="mb-1"><strong>Defeito relatado:</strong> {os_item['defeito'] or '-'}</p></div>
                <div class="col-12"><p class="mb-1"><strong>Diagnóstico:</strong> {os_item['diagnostico'] or 'Em análise'}</p></div>
            </div>

            <div class="section-title">03 PEÇAS E SERVIÇOS</div>
            <div class="table-responsive mb-1">
                <table class="table table-bordered table-custom align-middle mb-1">
                    <thead class="table-dark">
                        <tr>
                            <th>TIPO</th>
                            <th>DESCRIÇÃO</th>
                            <th class="text-center">QTD</th>
                            <th class="text-end">TOTAL (R$)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {itens_linhas_html}
                    </tbody>
                </table>
                <div class="text-end fw-bold text-primary" style="font-size: 12px;">
                    TOTAL GERAL: R$ {(os_item['valor'] or 0.0):.2f}
                </div>
            </div>

            <div class="footer-terms">
                <p class="mb-0"><strong>Garantia:</strong> 90 dias sobre serviços e peças. Não nos responsabilizamos por aparelhos após 90 dias sem retirada.</p>
            </div>

            <div class="row mt-2 text-center">
                <div class="col-6">
                    <div style="border-top: 1px solid #000; width: 85%; margin: auto; padding-top: 2px; font-size: 9px;">Assinatura do Cliente</div>
                </div>
                <div class="col-6">
                    <div style="border-top: 1px solid #000; width: 85%; margin: auto; padding-top: 2px; font-size: 9px;">Clínica do Hardware</div>
                </div>
            </div>
        </div>
        """

    print_template = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Ordem de Serviço - OS-{os_item['id']:04d}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body {{ background: #fff; color: #000; font-family: Arial, sans-serif; padding: 5px; font-size: 10px; }}
            .via-box {{ padding: 8px 12px; background: #fff; height: 48vh; box-sizing: border-box; display: flex; flex-direction: column; justify-content: space-between; }}
            .header-print {{ border-bottom: 2px solid #002060; padding-bottom: 4px; margin-bottom: 4px; }}
            .section-title {{ background-color: #f0f4f8; border-left: 4px solid #002060; padding: 2px 5px; font-weight: bold; font-size: 10px; margin-top: 4px; margin-bottom: 3px; text-transform: uppercase; color: #002060; }}
            .footer-terms {{ font-size: 9px; color: #555; background: #f9f9f9; padding: 3px; border: 1px solid #ddd; border-radius: 3px; margin-top: 3px; }}
            .logo-img {{ max-height: 35px; max-width: 120px; object-fit: contain; }}
            .table-custom th, .table-custom td {{ padding: 3px 5px !important; font-size: 10px; }}
            .linha-recorte {{ border-top: 2px dashed #666; margin: 4px 0; position: relative; text-align: center; }}
            .linha-recorte span {{ background: #fff; padding: 0 10px; font-size: 9px; color: #666; position: relative; top: -8px; font-weight: bold; text-transform: uppercase; }}
            @media print {{
                .no-print {{ display: none !important; }}
                body {{ padding: 0; margin: 0; }}
                @page {{ size: A4; margin: 5mm; }}
            }}
        </style>
    </head>
    <body onload="window.print()">
        {gerar_via_os("1ª VIA - CLIENTE")}
        <div class="linha-recorte"><span>✂️ DESTACAR / RECORTAR AQUI ✂️</span></div>
        {gerar_via_os("2ª VIA - EMPRESA")}

        <div class="text-center mt-2 no-print">
            <button onclick="window.print()" class="btn btn-primary btn-sm"><i class="fas fa-print"></i> Imprimir / Salvar PDF</button>
            <a href="/" class="btn btn-secondary btn-sm">Voltar</a>
        </div>
    </body>
    </html>
    """
    return print_template

@app.route('/os/imprimir_via_unica/<int:id>')
def imprimir_os_via_unica(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ordens_servico WHERE id = %s" if DATABASE_URL else "SELECT * FROM ordens_servico WHERE id = ?", (id,))
    os_item = cursor.fetchone()
    conn.close()
    if not os_item:
        flash("Ordem de Serviço não encontrada.", "danger")
        return redirect(url_for('index'))
    
    data_formatada = datetime.strptime(os_item['data_abertura'], "%Y-%m-%d").strftime("%d/%m/%Y") if os_item['data_abertura'] else ""

    itens_linhas_html = ""
    try:
        servicos_arr = json.loads(os_item['servicos_json']) if os_item['servicos_json'] else []
    except:
        servicos_arr = []

    if servicos_arr:
        for s in servicos_arr:
            subtotal = s['quantidade'] * s['valor_unitario']
            itens_linhas_html += f"<tr><td>Serviço</td><td>{s['nome']}</td><td class='text-center'>{s['quantidade']}</td><td class='text-end'>R$ {subtotal:.2f}</td></tr>"
    elif os_item['servico']:
        itens_linhas_html += f"<tr><td>Serviço</td><td>{os_item['servico']}</td><td class='text-center'>1</td><td class='text-end'>R$ {(os_item['valor_servico'] or 0.0):.2f}</td></tr>"

    try:
        pecas_arr = json.loads(os_item['pecas_json']) if os_item['pecas_json'] else []
    except:
        pecas_arr = []

    if pecas_arr:
        for p in pecas_arr:
            subtotal = p['quantidade'] * p['valor_unitario']
            itens_linhas_html += f"<tr><td>Peça</td><td>{p['nome']}</td><td class='text-center'>{p['quantidade']}</td><td class='text-end'>R$ {subtotal:.2f}</td></tr>"
    elif os_item['peca_utilizada']:
        itens_linhas_html += f"<tr><td>Peça</td><td>{os_item['peca_utilizada']}</td><td class='text-center'>1</td><td class='text-end'>R$ {(os_item['valor_pecas'] or 0.0):.2f}</td></tr>"

    print_template = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Ordem de Serviço (Via Única) - OS-{os_item['id']:04d}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body {{ background: #fff; color: #000; font-family: Arial, sans-serif; padding: 20px; font-size: 12px; }}
            .via-box {{ padding: 15px 20px; background: #fff; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; display: flex; flex-direction: column; justify-content: space-between; max-width: 800px; margin: auto; }}
            .header-print {{ border-bottom: 2px solid #002060; padding-bottom: 8px; margin-bottom: 10px; }}
            .section-title {{ background-color: #f0f4f8; border-left: 4px solid #002060; padding: 4px 8px; font-weight: bold; font-size: 12px; margin-top: 10px; margin-bottom: 6px; text-transform: uppercase; color: #002060; }}
            .footer-terms {{ font-size: 10px; color: #555; background: #f9f9f9; padding: 6px; border: 1px solid #ddd; border-radius: 3px; margin-top: 10px; }}
            .logo-img {{ max-height: 45px; max-width: 150px; object-fit: contain; }}
            @media print {{
                .no-print {{ display: none !important; }}
                body {{ padding: 0; margin: 0; }}
                @page {{ size: A4; margin: 10mm; }}
                .via-box {{ border: none; }}
            }}
        </style>
    </head>
    <body onload="window.print()">
        <div class="via-box">
            <div class="row header-print align-items-center">
                <div class="col-8 d-flex align-items-center">
                    <img src="/static/logo.png" alt="Logo" class="logo-img me-2" onerror="this.style.display='none'">
                    <div>
                        <h3 class="mb-1" style="font-weight: 900; color: #002060; font-size: 18px;">CLÍNICA DO HARDWARE</h3>
                        <p class="mb-0 small text-muted" style="font-size: 11px;"><strong>CNPJ:</strong> 70.017.290/0001-61 | <strong>Tel:</strong> (98) 9 8482-9705</p>
                    </div>
                </div>
                <div class="col-4 text-end">
                    <span class="badge bg-primary mb-1" style="font-size: 11px;">VIA DO CLIENTE</span>
                    <h5 class="text-danger mb-0" style="font-weight: bold; font-size: 13px;">ORDEM DE SERVIÇO</h5>
                    <h5 class="mb-0" style="color: #002060; font-size: 15px;"><strong>Nº OS-{os_item['id']:04d}</strong></h5>
                    <small class="text-muted" style="font-size: 11px;">Data: {data_formatada} | Status: <strong>{os_item['status']}</strong></small>
                </div>
            </div>

            <div class="section-title">01 DADOS DO CLIENTE</div>
            <div class="row mb-2">
                <div class="col-8"><p class="mb-1"><strong>Cliente:</strong> {os_item['cliente']}</p></div>
                <div class="col-4"><p class="mb-1"><strong>CPF/CNPJ:</strong> {os_item['cpf_cnpj'] or 'Não informado'}</p></div>
                <div class="col-6"><p class="mb-1"><strong>Contato:</strong> {os_item['contato'] or 'Não informado'}</p></div>
                <div class="col-6"><p class="mb-1"><strong>E-mail/End:</strong> {os_item['email_end'] or 'Não informado'}</p></div>
            </div>

            <div class="section-title">02 EQUIPAMENTO & AVALIAÇÃO TÉCNICA</div>
            <div class="row mb-2">
                <div class="col-4"><p class="mb-1"><strong>Tipo:</strong> {os_item['tipo_equip']}</p></div>
                <div class="col-4"><p class="mb-1"><strong>Marca:</strong> {os_item['marca'] or '-'}</p></div>
                <div class="col-4"><p class="mb-1"><strong>Modelo:</strong> {os_item['equipamento']}</p></div>
                <div class="col-6"><p class="mb-1"><strong>Nº Série:</strong> {os_item['ns_patrimonio'] or '-'}</p></div>
                <div class="col-6"><p class="mb-1"><strong>Acessórios:</strong> {os_item['acessorios'] or 'Nenhum'}</p></div>
                <div class="col-12"><p class="mb-1"><strong>Defeito relatado:</strong> {os_item['defeito'] or '-'}</p></div>
                <div class="col-12"><p class="mb-1"><strong>Diagnóstico:</strong> {os_item['diagnostico'] or 'Em análise'}</p></div>
            </div>

            <div class="section-title">03 PEÇAS E SERVIÇOS</div>
            <div class="table-responsive mb-2">
                <table class="table table-bordered align-middle mb-2">
                    <thead class="table-dark">
                        <tr>
                            <th>TIPO</th>
                            <th>DESCRIÇÃO</th>
                            <th class="text-center">QTD</th>
                            <th class="text-end">TOTAL (R$)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {itens_linhas_html}
                    </tbody>
                </table>
                <div class="text-end fw-bold text-primary" style="font-size: 14px;">
                    TOTAL GERAL: R$ {(os_item['valor'] or 0.0):.2f}
                </div>
            </div>

            <div class="footer-terms">
                <p class="mb-0"><strong>Garantia:</strong> 90 dias sobre serviços e peças. Não nos responsabilizamos por aparelhos após 90 dias sem retirada.</p>
            </div>

            <div class="row mt-4 text-center">
                <div class="col-6">
                    <div style="border-top: 1px solid #000; width: 80%; margin: auto; padding-top: 4px; font-size: 11px;">Assinatura do Cliente</div>
                </div>
                <div class="col-6">
                    <div style="border-top: 1px solid #000; width: 80%; margin: auto; padding-top: 4px; font-size: 11px;">Clínica do Hardware</div>
                </div>
            </div>
        </div>

        <div class="text-center mt-3 no-print">
            <button onclick="window.print()" class="btn btn-primary btn-sm"><i class="fas fa-print"></i> Imprimir / Salvar PDF</button>
            <a href="/" class="btn btn-secondary btn-sm">Voltar</a>
        </div>
    </body>
    </html>
    """
    return print_template

@app.route('/os/enviar_email/<int:id>')
def enviar_email_os(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ordens_servico WHERE id = %s" if DATABASE_URL else "SELECT * FROM ordens_servico WHERE id = ?", (id,))
    os_item = cursor.fetchone()
    conn.close()
    if not os_item or not os_item['email_end']:
        flash("E-mail do cliente não cadastrado nesta O.S.", "danger")
        return redirect(url_for('index'))
    
    data_formatada = datetime.strptime(os_item['data_abertura'], "%Y-%m-%d").strftime("%d/%m/%Y") if os_item['data_abertura'] else datetime.now().strftime("%d/%m/%Y")
    
    assunto = f"Envio de Ordem de Serviço Nº {os_item['id']:04d} - {os_item['equipamento']} | {os_item['cliente']}"
    corpo_html = f"""
    <div style="font-family: Arial, sans-serif; color: #333; padding: 25px; border: 1px solid #002060; border-radius: 8px; max-width: 600px; margin: auto; background-color: #ffffff;">
        <h2 style="color: #002060; border-bottom: 2px solid #002060; padding-bottom: 10px; margin-top: 0;">CLÍNICA DO HARDWARE</h2>
        <p>Prezado(a) <strong>{os_item['cliente']}</strong>,</p>
        <p>Espero que se encontre bem.</p>
        <p>Segue em anexo a <strong>Ordem de Serviço Nº {os_item['id']:04d}</strong> referente ao equipamento <strong>{os_item['tipo_equip']} {os_item['marca'] or ''} {os_item['equipamento']}</strong> (Patrimônio/Série: <strong>{os_item['ns_patrimonio'] or 'Não informado'}</strong>), entrada registrada em <strong>{data_formatada}</strong>.</p>
        
        <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #002060; margin: 15px 0; border-radius: 4px;">
            <p style="margin: 0 0 8px 0;"><strong>Resumo da Avaliação Técnica:</strong></p>
            <ul style="margin: 0; padding-left: 20px;">
                <li><strong>Status Atual:</strong> {os_item['status']}</li>
                <li><strong>Defeito Relatado:</strong> {os_item['defeito'] or 'Não especificado'}</li>
                <li><strong>Constatação / Diagnóstico Técnico:</strong> {os_item['diagnostico'] or 'Em análise'}</li>
                <li><strong>Valor Total:</strong> R$ {os_item['valor']:.2f}</li>
            </ul>
        </div>
        
        <p>Ficamos a aguardar a vossa validação para darmos início aos procedimentos necessários.</p>
        <p>Caso tenha alguma dúvida ou necessite de esclarecimentos adicionais, estamos à inteira disposição.</p>
        <br>
        <p style="margin-bottom: 0;">Com os melhores cumprimentos,</p>
        <p style="font-weight: bold; color: #002060; margin-top: 4px;">Clínica do Hardware</p>
        <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
        <p style="font-size: 12px; color: #666; text-align: center; margin: 0;">Tel: (98) 9 8482-9705 | São Luís - MA</p>
    </div>
    """
    
    html_pdf = imprimir_os(id)
    pdf_bytes = None
    try:
        import pdfkit
        pdf_bytes = pdfkit.from_string(html_pdf, False)
    except Exception:
        pdf_bytes = html_pdf.encode('utf-8')

    nome_pdf = f"Ordem_Servico_{os_item['id']:04d}.pdf"
    sucesso, mensagem = enviar_email_com_anexo_smtp(os_item['email_end'], assunto, corpo_html, pdf_bytes, nome_pdf)
    
    if sucesso:
        flash("E-mail com Ordem de Serviço em PDF enviado com sucesso pelo Gmail!", "success")
    else:
        flash(f"Erro ao enviar e-mail: {mensagem}", "danger")
        
    return redirect(url_for('index'))

@app.route('/os/status_rapido/<int:id>', methods=['POST'])
def status_rapido(id):
    dados = request.get_json()
    novo_status = dados.get('status')
    if novo_status:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE ordens_servico SET status = %s WHERE id = %s" if DATABASE_URL else "UPDATE ordens_servico SET status = ? WHERE id = ?", (novo_status, id))
        conn.commit()
        conn.close()
        return jsonify({'sucesso': True})
    return jsonify({'sucesso': False}), 400

@app.route('/os/nova', methods=['GET', 'POST'])
def nova_os():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        cliente = request.form['cliente']
        cpf_cnpj = request.form['cpf_cnpj']
        contato = request.form['contato']
        email_end = request.form['email_end']
        tipo_equip = request.form['tipo_equip']
        marca = request.form['marca']
        equipamento = request.form['equipamento']
        ns_patrimonio = request.form['ns_patrimonio']
        acessorios = request.form['acessorios']
        condicao = request.form['condicao']
        status = request.form['status']
        defeito = request.form['defeito']
        diagnostico = request.form['diagnostico']
        
        servicos_json = request.form['servicos_json']
        pecas_json = request.form['pecas_json']

        servicos_arr = json.loads(servicos_json) if servicos_json else []
        servico_str = ", ".join([f"{s['quantidade']}x {s['nome']} (R$ {s['valor_unitario']:.2f} un)" for s in servicos_arr])

        pecas_arr = json.loads(pecas_json) if pecas_json else []
        peca_utilizada_str = ", ".join([f"{p['quantidade']}x {p['nome']} (R$ {p['valor_unitario']:.2f} un)" for p in pecas_arr])

        valor_pecas = float(request.form['valor_pecas'] or 0)
        valor_servico = float(request.form['valor_servico'] or 0)
        valor_total = valor_pecas + valor_servico
        data_hoje = datetime.now().strftime("%Y-%m-%d")

        if DATABASE_URL:
            cursor.execute("""INSERT INTO ordens_servico 
                              (cliente, cpf_cnpj, contato, email_end, tipo_equip, marca, equipamento, ns_patrimonio, 
                               acessorios, condicao, status, defeito, diagnostico, servico, servicos_json, peca_utilizada, pecas_json, valor_pecas, valor_servico, valor, data_abertura) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                           (cliente, cpf_cnpj, contato, email_end, tipo_equip, marca, equipamento, ns_patrimonio,
                            acessorios, condicao, status, defeito, diagnostico, servico_str, servicos_json, peca_utilizada_str, pecas_json, valor_pecas, valor_servico, valor_total, data_hoje))
            os_id = cursor.fetchone()['id']
        else:
            cursor.execute("""INSERT INTO ordens_servico 
                              (cliente, cpf_cnpj, contato, email_end, tipo_equip, marca, equipamento, ns_patrimonio, 
                               acessorios, condicao, status, defeito, diagnostico, servico, servicos_json, peca_utilizada, pecas_json, valor_pecas, valor_servico, valor, data_abertura) 
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                           (cliente, cpf_cnpj, contato, email_end, tipo_equip, marca, equipamento, ns_patrimonio,
                            acessorios, condicao, status, defeito, diagnostico, servico_str, servicos_json, peca_utilizada_str, pecas_json, valor_pecas, valor_servico, valor_total, data_hoje))
            os_id = cursor.lastrowid

        cursor.execute("INSERT INTO boletos (cliente, numero_documento, valor, data_vencimento, status) VALUES (%s, %s, %s, %s, %s)" if DATABASE_URL else
                       "INSERT INTO boletos (cliente, numero_documento, valor, data_vencimento, status) VALUES (?, ?, ?, ?, ?)",
                       (cliente, f"OS-{os_id:04d}", valor_total, data_hoje, "Gerado (Aguardando Pagamento)"))
        conn.commit()
        conn.close()
        flash("Ordem de Serviço salva e Boleto gerado com sucesso!", "success")
        return redirect(url_for('index'))

    cursor.execute("SELECT * FROM ordem_entrada ORDER BY id DESC")
    entradas_pendentes = cursor.fetchall()
    cursor.execute("SELECT * FROM servicos_cadastrados ORDER BY nome_servico ASC")
    lista_servicos = cursor.fetchall()
    cursor.execute("SELECT * FROM pecas_estoque ORDER BY nome_peca ASC")
    lista_pecas = cursor.fetchall()
    conn.close()
    
    options_entradas = "".join([f"<option value='{e['id']}' data-cliente='{e['cliente']}' data-doc='{e['cpf_cnpj'] or ''}' data-contato='{e['contato'] or ''}' data-email='{e['email'] or ''}' data-tipo='{e['tipo_equip']}' data-marca='{e['marca'] or ''}' data-equip='{e['equipamento']}' data-ns='{e['ns_patrimonio'] or ''}' data-acessorios='{e['acessorios'] or ''}' data-condicao='{e['condicao'] or ''}' data-defeito='{e['defeito'] or ''}'>ENT-{e['id']:04d} - {e['cliente']} ({e['equipamento']})</option>" for e in entradas_pendentes])
    servicos_dict_list = [{"nome_servico": s["nome_servico"], "valor_padrao": s["valor_padrao"]} for s in lista_servicos]
    pecas_dict_list = [{"nome_peca": p["nome_peca"], "quantidade": p["quantidade"], "valor_venda": p["valor_venda"]} for p in lista_pecas]

    html_page = BASE_TEMPLATE.replace("{% block content %}{% endblock %}", f"""
    <div class="header-custom">
        <h2><i class="fas fa-plus-circle"></i> Nova Ordem de Serviço Direta</h2>
    </div>
    <div class="card p-4">
        <form method="POST">
            <input type="hidden" id="servicos_json_input" name="servicos_json">
            <input type="hidden" id="pecas_json_input" name="pecas_json">
            <div class="row g-3 mb-4 p-3 bg-light border rounded">
                <div class="col-md-12">
                    <label class="form-label text-primary"><strong><i class="fas fa-search"></i> Puxar Dados da Ordem de Entrada (Check-in):</strong></label>
                    <select class="form-select border-primary" onchange="preencherDadosEntrada(this)">
                        <option value="">-- Selecione um equipamento da recepção para preencher automaticamente --</option>
                        {options_entradas}
                    </select>
                </div>
            </div>

            <div class="row g-3">
                <div class="col-md-6">
                    <label class="form-label">Cliente / Razão Social:</label>
                    <input type="text" class="form-control" id="cliente_field" name="cliente" required>
                </div>
                <div class="col-md-6">
                    <label class="form-label">CPF / CNPJ:</label>
                    <input type="text" class="form-control" id="cpf_cnpj_field" name="cpf_cnpj" placeholder="Digite o CNPJ" onblur="consultarCnpjCompleto('cpf_cnpj_field', 'cliente_field', 'contato_field', 'email_field')">
                </div>
                <div class="col-md-6">
                    <label class="form-label">Contato (WhatsApp):</label>
                    <input type="text" class="form-control" id="contato_field" name="contato">
                </div>
                <div class="col-md-6">
                    <label class="form-label">E-mail / Endereço:</label>
                    <input type="email" class="form-control" id="email_field" name="email_end">
                </div>
                <div class="col-md-4">
                    <label class="form-label">Tipo de Equipamento:</label>
                    <input type="text" class="form-control" name="tipo_equip" value="NOTEBOOK">
                </div>
                <div class="col-md-4">
                    <label class="form-label">Marca:</label>
                    <input type="text" class="form-control" name="marca" placeholder="Ex: Dell">
                </div>
                <div class="col-md-4">
                    <label class="form-label">Modelo:</label>
                    <input type="text" class="form-control" name="equipamento" required placeholder="Ex: Inspiron 15">
                </div>
                <div class="col-md-6">
                    <label class="form-label">Nº de Série / Patrimônio:</label>
                    <input type="text" class="form-control" name="ns_patrimonio">
                </div>
                <div class="col-md-6">
                    <label class="form-label">Acessórios:</label>
                    <input type="text" class="form-control" name="acessorios" placeholder="Ex: Carregador, Bolsa">
                </div>
                <div class="col-md-12">
                    <label class="form-label">Condição Visual:</label>
                    <input type="text" class="form-control" name="condicao">
                </div>
                <div class="col-md-6">
                    <label class="form-label">Status Inicial:</label>
                    <select class="form-select" name="status">
                        <option value="Aguardando Aprovação">Aguardando Aprovação</option>
                        <option value="Em Execução">Em Execução</option>
                        <option value="Executado">Executado</option>
                    </select>
                </div>
                <div class="col-md-6">
                    <label class="form-label">Defeito Relatado:</label>
                    <textarea class="form-control" name="defeito" rows="2"></textarea>
                </div>
                <div class="col-md-12">
                    <label class="form-label">Diagnóstico Técnico / Constatação:</label>
                    <textarea class="form-control" name="diagnostico" rows="2"></textarea>
                </div>

                <div class="col-md-12 p-3 bg-light border rounded">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <label class="form-label fw-bold mb-0 text-primary"><i class="fas fa-tools"></i> Serviços a Executar (Múltiplos Serviços & Quantidade):</label>
                        <button type="button" class="btn btn-sm btn-primary" onclick="adicionarLinhaServico()"><i class="fas fa-plus"></i> Adicionar Serviço</button>
                    </div>
                    <div id="container-servicos"></div>
                </div>

                <div class="col-md-12 p-3 bg-light border rounded">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <label class="form-label fw-bold mb-0"><i class="fas fa-boxes"></i> Peças Utilizadas (Múltiplas Peças & Quantidade):</label>
                        <button type="button" class="btn btn-sm btn-primary" onclick="adicionarLinhaPeca()"><i class="fas fa-plus"></i> Adicionar Peça</button>
                    </div>
                    <div id="container-pecas"></div>
                </div>

                <div class="col-md-4">
                    <label class="form-label">Valor Peças (R$):</label>
                    <input type="number" step="0.01" class="form-control bg-white" id="valor_pecas_input" name="valor_pecas" value="0.00" readonly>
                </div>
                <div class="col-md-4">
                    <label class="form-label">Valor Serviços (R$):</label>
                    <input type="number" step="0.01" class="form-control bg-white" id="valor_servico_input" name="valor_servico" value="0.00" readonly>
                </div>
                <div class="col-md-4">
                    <label class="form-label text-success fw-bold">Valor Total (R$):</label>
                    <input type="text" class="form-control bg-light fw-bold text-success" id="valor_total_input" value="0.00" readonly>
                </div>
            </div>
            <div class="mt-4">
                <button type="submit" class="btn btn-success"><i class="fas fa-save"></i> Salvar O.S. & Gerar Boleto</button>
                <a href="/" class="btn btn-secondary">Voltar</a>
            </div>
        </form>
    </div>
    <script>
        inicializarServicosDisponiveis({json.dumps(servicos_dict_list)});
        inicializarPecasDisponiveis({json.dumps(pecas_dict_list)});
        adicionarLinhaServico();
    </script>
    """)
    return render_template_string(html_page, active_tab='os')

@app.route('/os/editar/<int:id>', methods=['GET', 'POST'])
def editar_os(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ordens_servico WHERE id = %s" if DATABASE_URL else "SELECT * FROM ordens_servico WHERE id = ?", (id,))
    os_item = cursor.fetchone()
    
    if request.method == 'POST':
        cliente = request.form['cliente']
        cpf_cnpj = request.form['cpf_cnpj']
        contato = request.form['contato']
        email_end = request.form['email_end']
        tipo_equip = request.form['tipo_equip']
        marca = request.form['marca']
        equipamento = request.form['equipamento']
        ns_patrimonio = request.form['ns_patrimonio']
        acessorios = request.form['acessorios']
        condicao = request.form['condicao']
        status = request.form['status']
        defeito = request.form['defeito']
        diagnostico = request.form['diagnostico']
        
        servicos_json = request.form['servicos_json']
        pecas_json = request.form['pecas_json']

        servicos_arr = json.loads(servicos_json) if servicos_json else []
        servico_str = ", ".join([f"{s['quantidade']}x {s['nome']} (R$ {s['valor_unitario']:.2f} un)" for s in servicos_arr])

        pecas_arr = json.loads(pecas_json) if pecas_json else []
        peca_utilizada_str = ", ".join([f"{p['quantidade']}x {p['nome']} (R$ {p['valor_unitario']:.2f} un)" for p in pecas_arr])

        valor_pecas = float(request.form['valor_pecas'] or 0)
        valor_servico = float(request.form['valor_servico'] or 0)
        valor_total = valor_pecas + valor_servico

        cursor.execute("""UPDATE ordens_servico SET 
                        cliente = %s, cpf_cnpj = %s, contato = %s, email_end = %s, 
                        tipo_equip = %s, marca = %s, equipamento = %s, ns_patrimonio = %s, 
                        acessorios = %s, condicao = %s, status = ?, 
                        defeito = %s, diagnostico = %s, servico = %s, servicos_json = %s, peca_utilizada = %s, pecas_json = %s,
                        valor_pecas = %s, valor_servico = %s, valor = %s WHERE id = %s""" if DATABASE_URL else
                       """UPDATE ordens_servico SET 
                        cliente = ?, cpf_cnpj = ?, contato = ?, email_end = ?, 
                        tipo_equip = ?, marca = ?, equipamento = ?, ns_patrimonio = ?, 
                        acessorios = ?, condicao = ?, status = ?, 
                        defeito = ?, diagnostico = ?, servico = ?, servicos_json = ?, peca_utilizada = ?, pecas_json = ?,
                        valor_pecas = ?, valor_servico = ?, valor = ? WHERE id = ?""",
                   (cliente, cpf_cnpj, contato, email_end, tipo_equip, marca, equipamento, ns_patrimonio,
                    acessorios, condicao, status, defeito, diagnostico, servico_str, servicos_json, peca_utilizada_str, pecas_json,
                    valor_pecas, valor_servico, valor_total, id))
        
        cursor.execute("UPDATE boletos SET cliente = %s, valor = %s WHERE numero_documento = %s" if DATABASE_URL else
                       "UPDATE boletos SET cliente = ?, valor = ? WHERE numero_documento = ?",
                   (cliente, valor_total, f"OS-{id:04d}"))
        conn.commit()
        conn.close()
        flash("Ordem de Serviço atualizada com sucesso!", "success")
        return redirect(url_for('index'))

    cursor.execute("SELECT * FROM servicos_cadastrados ORDER BY nome_servico ASC")
    lista_servicos = cursor.fetchall()
    cursor.execute("SELECT * FROM pecas_estoque ORDER BY nome_peca ASC")
    lista_pecas = cursor.fetchall()
    conn.close()

    servicos_dict_list = [{"nome_servico": s["nome_servico"], "valor_padrao": s["valor_padrao"]} for s in lista_servicos]
    pecas_dict_list = [{"nome_peca": p["nome_peca"], "quantidade": p["quantidade"], "valor_venda": p["valor_venda"]} for p in lista_pecas]
    
    try:
        servicos_atuais_json = os_item['servicos_json'] or '[]'
    except:
        servicos_atuais_json = '[]'

    try:
        pecas_atuais_json = os_item['pecas_json'] or '[]'
    except:
        pecas_atuais_json = '[]'

    html_page = BASE_TEMPLATE.replace("{% block content %}{% endblock %}", f"""
    <div class="header-custom">
        <h2><i class="fas fa-edit"></i> Editar Ordem de Serviço Nº {os_item['id']:04d}</h2>
    </div>
    <div class="card p-4">
        <form method="POST">
            <input type="hidden" id="servicos_json_input" name="servicos_json">
            <input type="hidden" id="pecas_json_input" name="pecas_json">
            <div class="row g-3">
                <div class="col-md-6">
                    <label class="form-label">Cliente:</label>
                    <input type="text" class="form-control" id="cliente_field" name="cliente" value="{os_item['cliente'] or ''}" required>
                </div>
                <div class="col-md-6">
                    <label class="form-label">CPF / CNPJ:</label>
                    <input type="text" class="form-control" id="cpf_cnpj_field" name="cpf_cnpj" value="{os_item['cpf_cnpj'] or ''}" onblur="consultarCnpjCompleto('cpf_cnpj_field', 'cliente_field', 'contato_field', 'email_field')">
                </div>
                <div class="col-md-6">
                    <label class="form-label">Contato:</label>
                    <input type="text" class="form-control" id="contato_field" name="contato" value="{os_item['contato'] or ''}">
                </div>
                <div class="col-md-6">
                    <label class="form-label">E-mail / Endereço:</label>
                    <input type="email" class="form-control" id="email_field" name="email_end" value="{os_item['email_end'] or ''}">
                </div>
                <div class="col-md-4">
                    <label class="form-label">Tipo:</label>
                    <input type="text" class="form-control" name="tipo_equip" value="{os_item['tipo_equip'] or ''}">
                </div>
                <div class="col-md-4">
                    <label class="form-label">Marca:</label>
                    <input type="text" class="form-control" name="marca" value="{os_item['marca'] or ''}">
                </div>
                <div class="col-md-4">
                    <label class="form-label">Modelo:</label>
                    <input type="text" class="form-control" name="equipamento" value="{os_item['equipamento'] or ''}">
                </div>
                <div class="col-md-6">
                    <label class="form-label">Nº Série:</label>
                    <input type="text" class="form-control" name="ns_patrimonio" value="{os_item['ns_patrimonio'] or ''}">
                </div>
                <div class="col-md-6">
                    <label class="form-label">Acessórios:</label>
                    <input type="text" class="form-control" name="acessorios" value="{os_item['acessorios'] or ''}">
                </div>
                <div class="col-md-12">
                    <label class="form-label">Condição:</label>
                    <input type="text" class="form-control" name="condicao" value="{os_item['condicao'] or ''}">
                </div>
                <div class="col-md-6">
                    <label class="form-label">Status:</label>
                    <select class="form-select" name="status">
                        <option value="Aguardando Aprovação" {'selected' if os_item['status'] == 'Aguardando Aprovação' else ''}>Aguardando Aprovação</option>
                        <option value="Em Execução" {'selected' if os_item['status'] == 'Em Execução' else ''}>Em Execução</option>
                        <option value="Executado" {'selected' if os_item['status'] == 'Executado' else ''}>Executado</option>
                    </select>
                </div>
                <div class="col-md-6">
                    <label class="form-label">Defeito:</label>
                    <textarea class="form-control" name="defeito" rows="2">{os_item['defeito'] or ''}</textarea>
                </div>
                <div class="col-md-12">
                    <label class="form-label">Diagnóstico Técnico / Constatação:</label>
                    <textarea class="form-control" name="diagnostico" rows="2">{os_item['diagnostico'] or ''}</textarea>
                </div>

                <div class="col-md-12 p-3 bg-light border rounded">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <label class="form-label fw-bold mb-0 text-primary"><i class="fas fa-tools"></i> Serviços a Executar (Múltiplos Serviços & Quantidade):</label>
                        <button type="button" class="btn btn-sm btn-primary" onclick="adicionarLinhaServico()"><i class="fas fa-plus"></i> Adicionar Serviço</button>
                    </div>
                    <div id="container-servicos"></div>
                </div>

                <div class="col-md-12 p-3 bg-light border rounded">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <label class="form-label fw-bold mb-0"><i class="fas fa-boxes"></i> Peças Utilizadas (Múltiplas Peças & Quantidade):</label>
                        <button type="button" class="btn btn-sm btn-primary" onclick="adicionarLinhaPeca()"><i class="fas fa-plus"></i> Adicionar Peça</button>
                    </div>
                    <div id="container-pecas"></div>
                </div>

                <div class="col-md-4">
                    <label class="form-label">Valor Peças (R$):</label>
                    <input type="number" step="0.01" class="form-control bg-white" id="valor_pecas_input" name="valor_pecas" value="{os_item['valor_pecas'] or 0.00}" readonly>
                </div>
                <div class="col-md-4">
                    <label class="form-label">Valor Serviços (R$):</label>
                    <input type="number" step="0.01" class="form-control bg-white" id="valor_servico_input" name="valor_servico" value="{os_item['valor_servico'] or 0.00}" readonly>
                </div>
                <div class="col-md-4">
                    <label class="form-label text-success fw-bold">Valor Total (R$):</label>
                    <input type="text" class="form-control bg-light fw-bold text-success" id="valor_total_input" value="0.00" readonly>
                </div>
            </div>
            <div class="mt-4">
                <button type="submit" class="btn btn-primary"><i class="fas fa-save"></i> Salvar Alterações</button>
                <a href="/" class="btn btn-secondary">Voltar</a>
            </div>
        </form>
    </div>
    <script>
        inicializarServicosDisponiveis({json.dumps(servicos_dict_list)});
        inicializarPecasDisponiveis({json.dumps(pecas_dict_list)});
        
        let servicosExistentes = {servicos_atuais_json};
        if(servicosExistentes.length > 0) {{
            servicosExistentes.forEach(s => {{
                adicionarLinhaServico(s.nome, s.quantidade, s.valor_unitario);
            }});
        }} else {{
            let servicoAntigo = "{os_item['servico'] or ''}";
            let valorServicoAntigo = {os_item['valor_servico'] or 0.0};
            if(servicoAntigo) {{
                adicionarLinhaServico(servicoAntigo, 1, valorServicoAntigo);
            }} else {{
                adicionarLinhaServico();
            }}
        }}

        let pecasExistentes = {pecas_atuais_json};
        if(pecasExistentes.length > 0) {{
            pecasExistentes.forEach(p => {{
                adicionarLinhaPeca(p.nome, p.quantidade, p.valor_unitario);
            }});
        }} else {{
            adicionarLinhaPeca();
        }}
    </script>
    """)
    return render_template_string(html_page, active_tab='os', os_item=os_item)

@app.route('/os/excluir/<int:id>')
def excluir_os(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM boletos WHERE numero_documento = %s" if DATABASE_URL else "DELETE FROM boletos WHERE numero_documento = ?", (f"OS-{id:04d}",))
    cursor.execute("DELETE FROM ordens_servico WHERE id = %s" if DATABASE_URL else "DELETE FROM ordens_servico WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Ordem de Serviço excluída com sucesso!", "success")
    return redirect(url_for('index'))

@app.route('/clientes', methods=['GET', 'POST'])
def clientes():
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        nome = request.form['nome']
        cpf_cnpj = request.form['cpf_cnpj']
        contato = request.form['contato']
        email = request.form['email']
        cep = request.form['cep']
        rua = request.form['rua']
        numero = request.form['numero']
        bairro = request.form['bairro']
        complemento = request.form['complemento']
        cidade_uf = request.form['cidade_uf']

        cursor.execute("""INSERT INTO clientes (nome, cpf_cnpj, contato, email, cep, rua, numero, bairro, complemento, cidade_uf) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""" if DATABASE_URL else
                       """INSERT INTO clientes (nome, cpf_cnpj, contato, email, cep, rua, numero, bairro, complemento, cidade_uf) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                   (nome, cpf_cnpj, contato, email, cep, rua, numero, bairro, complemento, cidade_uf))
        conn.commit()
        conn.close()
        flash("Cliente cadastrado com sucesso!", "success")
        return redirect(url_for('clientes'))
    
    cursor.execute("SELECT * FROM clientes ORDER BY id DESC")
    lista = cursor.fetchall()
    conn.close()

    linhas_clientes = "".join([
        f"<tr>"
        f"<td>{c['id']}</td>"
        f"<td>{c['nome']}</td>"
        f"<td>{c['cpf_cnpj'] or ''}</td>"
        f"<td>{c['contato'] or ''}</td>"
        f"<td>{c['cidade_uf'] or ''}</td>"
        f"<td>"
        f"<a href='/clientes/editar/{c['id']}' class='btn btn-sm btn-warning'><i class='fas fa-edit'></i></a> "
        f"<a href='/clientes/excluir/{c['id']}' class='btn btn-sm btn-danger' onclick=\"return confirm('Deseja excluir este cliente?');\"><i class='fas fa-trash'></i></a>"
        f"</td>"
        f"</tr>"
        for c in lista
    ]) if lista else "<tr><td colspan='6' class='text-center text-muted'>Nenhum cliente cadastrado.</td></tr>"

    html_page = BASE_TEMPLATE.replace("{% block content %}{% endblock %}", f"""
    <div class="header-custom">
        <h2><i class="fas fa-users"></i> Gerenciamento de Clientes</h2>
    </div>
    <div class="card p-4 mb-4">
        <h4>Cadastrar Novo Cliente (Consulta Automática de CNPJ e CEP)</h4>
        <form method="POST" class="row g-3">
            <div class="col-md-6"><input type="text" class="form-control" id="cliente_field" name="nome" placeholder="Nome / Razão Social" required></div>
            <div class="col-md-6"><input type="text" class="form-control" id="cpf_cnpj_field" name="cpf_cnpj" placeholder="CPF / CNPJ (Digite o CNPJ para preencher tudo)" onblur="consultarCnpjCompleto('cpf_cnpj_field', 'cliente_field', 'contato_field', 'email_field', 'cep_field', 'rua_field', 'num_field', 'bairro_field', 'compl_field', 'cidade_field')"></div>
            <div class="col-md-6"><input type="text" class="form-control" id="contato_field" name="contato" placeholder="Contato WhatsApp / Telefone"></div>
            <div class="col-md-6"><input type="email" class="form-control" id="email_field" name="email" placeholder="E-mail"></div>
            
            <div class="col-md-3"><input type="text" class="form-control" id="cep_field" name="cep" placeholder="CEP" onblur="consultarCep('cep_field', 'rua_field', 'bairro_field', 'cidade_field')"></div>
            <div class="col-md-6"><input type="text" class="form-control" id="rua_field" name="rua" placeholder="Rua / Logradouro"></div>
            <div class="col-md-3"><input type="text" class="form-control" id="num_field" name="numero" placeholder="Número"></div>
            <div class="col-md-4"><input type="text" class="form-control" id="bairro_field" name="bairro" placeholder="Bairro"></div>
            <div class="col-md-4"><input type="text" class="form-control" id="compl_field" name="complemento" placeholder="Complemento"></div>
            <div class="col-md-4"><input type="text" class="form-control" id="cidade_field" name="cidade_uf" placeholder="Cidade / UF"></div>

            <div class="col-12"><button type="submit" class="btn btn-primary"><i class="fas fa-save"></i> Salvar Cliente</button></div>
        </form>
    </div>
    <div class="card p-3">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h4 class="mb-0">Lista de Clientes Cadastrados</h4>
            <div style="width: 300px;">
                <input type="text" id="filtroClientes" class="form-control form-control-sm" placeholder="🔍 Filtrar clientes..." onkeyup="filtrarTabela('filtroClientes', 'tabelaClientes')">
            </div>
        </div>
        <div class="table-responsive">
            <table id="tabelaClientes" class="table table-striped align-middle">
                <thead class="table-dark">
                    <tr><th>ID</th><th>Nome / Razão Social</th><th>CPF / CNPJ</th><th>Contato</th><th>Cidade/UF</th><th>Ações</th></tr>
                </thead>
                <tbody>
                    {linhas_clientes}
                </tbody>
            </table>
        </div>
    </div>
    """)
    return render_template_string(html_page, active_tab='clientes', lista=lista)

@app.route('/clientes/editar/<int:id>', methods=['GET', 'POST'])
def editar_cliente(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clientes WHERE id = %s" if DATABASE_URL else "SELECT * FROM clientes WHERE id = ?", (id,))
    c = cursor.fetchone()
    
    if request.method == 'POST':
        nome = request.form['nome']
        cpf_cnpj = request.form['cpf_cnpj']
        contato = request.form['contato']
        email = request.form['email']
        cep = request.form['cep']
        rua = request.form['rua']
        numero = request.form['numero']
        bairro = request.form['bairro']
        complemento = request.form['complemento']
        cidade_uf = request.form['cidade_uf']

        cursor.execute("""UPDATE clientes SET nome = %s, cpf_cnpj = %s, contato = %s, email = ?, 
                        cep = %s, rua = %s, numero = %s, bairro = %s, complemento = %s, cidade_uf = %s WHERE id = %s""" if DATABASE_URL else
                       """UPDATE clientes SET nome = ?, cpf_cnpj = ?, contato = ?, email = ?, 
                        cep = ?, rua = ?, numero = ?, bairro = ?, complemento = ?, cidade_uf = ? WHERE id = ?""",
                   (nome, cpf_cnpj, contato, email, cep, rua, numero, bairro, complemento, cidade_uf, id))
        conn.commit()
        conn.close()
        flash("Cliente atualizado com sucesso!", "success")
        return redirect(url_for('clientes'))

    conn.close()
    html_page = BASE_TEMPLATE.replace("{% block content %}{% endblock %}", f"""
    <div class="header-custom">
        <h2><i class="fas fa-edit"></i> Editar Cliente (ID: {c['id']})</h2>
    </div>
    <div class="card p-4">
        <form method="POST" class="row g-3">
            <div class="col-md-6"><label class="form-label">Nome / Razão Social:</label><input type="text" class="form-control" id="cliente_field" name="nome" value="{c['nome'] or ''}" required></div>
            <div class="col-md-6"><label class="form-label">CPF / CNPJ:</label><input type="text" class="form-control" id="cpf_cnpj_field" name="cpf_cnpj" value="{c['cpf_cnpj'] or ''}" onblur="consultarCnpjCompleto('cpf_cnpj_field', 'cliente_field', 'contato_field', 'email_field', 'cep_field', 'rua_field', 'num_field', 'bairro_field', 'compl_field', 'cidade_field')"></div>
            <div class="col-md-6"><label class="form-label">Contato:</label><input type="text" class="form-control" id="contato_field" name="contato" value="{c['contato'] or ''}"></div>
            <div class="col-md-6"><label class="form-label">E-mail:</label><input type="email" class="form-control" id="email_field" name="email" value="{c['email'] or ''}"></div>
            
            <div class="col-md-3"><label class="form-label">CEP:</label><input type="text" class="form-control" id="cep_field" name="cep" value="{c['cep'] or ''}" onblur="consultarCep('cep_field', 'rua_field', 'bairro_field', 'cidade_field')"></div>
            <div class="col-md-6"><label class="form-label">Rua:</label><input type="text" class="form-control" id="rua_field" name="rua" value="{c['rua'] or ''}"></div>
            <div class="col-md-3"><label class="form-label">Número:</label><input type="text" class="form-control" id="num_field" name="numero" value="{c['numero'] or ''}"></div>
            <div class="col-md-4"><label class="form-label">Bairro:</label><input type="text" class="form-control" id="bairro_field" name="bairro" value="{c['bairro'] or ''}"></div>
            <div class="col-md-4"><label class="form-label">Complemento:</label><input type="text" class="form-control" id="compl_field" name="complemento" value="{c['complemento'] or ''}"></div>
            <div class="col-md-4"><label class="form-label">Cidade / UF:</label><input type="text" class="form-control" id="cidade_field" name="cidade_uf" value="{c['cidade_uf'] or ''}"></div>

            <div class="col-12 mt-4">
                <button type="submit" class="btn btn-primary"><i class="fas fa-save"></i> Salvar Alterações</button>
                <a href="/clientes" class="btn btn-secondary">Voltar</a>
            </div>
        </form>
    </div>
    """)
    return render_template_string(html_page, active_tab='clientes')

@app.route('/clientes/excluir/<int:id>')
def excluir_cliente(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clientes WHERE id = %s" if DATABASE_URL else "DELETE FROM clientes WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Cliente excluído com sucesso!", "success")
    return redirect(url_for('clientes'))

@app.route('/servicos', methods=['GET', 'POST'])
def servicos():
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        nome = request.form['nome_servico']
        desc = request.form['descricao']
        valor = float(request.form['valor_padrao'] or 0)
        cursor.execute("INSERT INTO servicos_cadastrados (nome_servico, descricao, valor_padrao) VALUES (%s, %s, %s)" if DATABASE_URL else "INSERT INTO servicos_cadastrados (nome_servico, descricao, valor_padrao) VALUES (?, ?, ?)", (nome, desc, valor))
        conn.commit()
        conn.close()
        flash("Serviço cadastrado com sucesso!", "success")
        return redirect(url_for('servicos'))
    cursor.execute("SELECT * FROM servicos_cadastrados")
    lista = cursor.fetchall()
    conn.close()

    linhas_servicos = "".join([
        f"<tr>"
        f"<td>{s['id']}</td>"
        f"<td>{s['nome_servico']}</td>"
        f"<td>{s['descricao'] or ''}</td>"
        f"<td>R$ {s['valor_padrao']:.2f}</td>"
        f"<td>"
        f"<a href='/servicos/editar/{s['id']}' class='btn btn-sm btn-warning' title='Editar'><i class='fas fa-edit'></i></a> "
        f"<a href='/servicos/excluir/{s['id']}' class='btn btn-sm btn-danger' onclick=\"return confirm('Deseja excluir este serviço?');\" title='Excluir'><i class='fas fa-trash'></i></a>"
        f"</td>"
        f"</tr>"
        for s in lista
    ]) if lista else "<tr><td colspan='5' class='text-center text-muted'>Nenhum serviço cadastrado.</td></tr>"

    html_page = BASE_TEMPLATE.replace("{% block content %}{% endblock %}", f"""
    <div class="header-custom"><h2><i class="fas fa-tools"></i> Cadastro de Serviços</h2></div>
    <div class="card p-4 mb-4">
        <form method="POST" class="row g-3">
            <div class="col-md-5"><input type="text" class="form-control" name="nome_servico" placeholder="Nome do Serviço" required></div>
            <div class="col-md-4"><input type="number" step="0.01" class="form-control" name="valor_padrao" placeholder="Valor Padrão (R$)" required></div>
            <div class="col-md-3"><button type="submit" class="btn btn-primary w-100"><i class="fas fa-save"></i> Salvar Serviço</button></div>
            <div class="col-12"><input type="text" class="form-control" name="descricao" placeholder="Descrição Detalhada"></div>
        </form>
    </div>
    <div class="card p-3">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h4 class="mb-0">Serviços Cadastrados</h4>
            <div style="width: 300px;">
                <input type="text" id="filtroServicos" class="form-control form-control-sm" placeholder="🔍 Filtrar serviços..." onkeyup="filtrarTabela('filtroServicos', 'tabelaServicos')">
            </div>
        </div>
        <div class="table-responsive">
            <table id="tabelaServicos" class="table table-striped align-middle">
                <thead class="table-dark"><tr><th>ID</th><th>Serviço</th><th>Descrição</th><th>Valor Padrão</th><th>Ações</th></tr></thead>
                <tbody>
                    {linhas_servicos}
                </tbody>
            </table>
        </div>
    </div>
    """)
    return render_template_string(html_page, active_tab='servicos', lista=lista)

@app.route('/servicos/editar/<int:id>', methods=['GET', 'POST'])
def editar_servico(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM servicos_cadastrados WHERE id = %s" if DATABASE_URL else "SELECT * FROM servicos_cadastrados WHERE id = ?", (id,))
    s = cursor.fetchone()
    
    if request.method == 'POST':
        nome = request.form['nome_servico']
        desc = request.form['descricao']
        valor = float(request.form['valor_padrao'] or 0)
        cursor.execute("UPDATE servicos_cadastrados SET nome_servico = %s, descricao = %s, valor_padrao = %s WHERE id = %s" if DATABASE_URL else "UPDATE servicos_cadastrados SET nome_servico = ?, descricao = ?, valor_padrao = ? WHERE id = ?",
                   (nome, desc, valor, id))
        conn.commit()
        conn.close()
        flash("Serviço atualizado com sucesso!", "success")
        return redirect(url_for('servicos'))

    conn.close()
    html_page = BASE_TEMPLATE.replace("{% block content %}{% endblock %}", f"""
    <div class="header-custom"><h2><i class="fas fa-edit"></i> Editar Serviço (ID: {s['id']})</h2></div>
    <div class="card p-4">
        <form method="POST" class="row g-3">
            <div class="col-md-6"><label class="form-label">Nome do Serviço:</label><input type="text" class="form-control" name="nome_servico" value="{s['nome_servico'] or ''}" required></div>
            <div class="col-md-6"><label class="form-label">Valor Padrão (R$):</label><input type="number" step="0.01" class="form-control" name="valor_padrao" value="{s['valor_padrao'] or 0.00}" required></div>
            <div class="col-12"><label class="form-label">Descrição Detalhada:</label><input type="text" class="form-control" name="descricao" value="{s['descricao'] or ''}"></div>
            <div class="col-12 mt-4">
                <button type="submit" class="btn btn-primary"><i class="fas fa-save"></i> Salvar Alterações</button>
                <a href="/servicos" class="btn btn-secondary">Voltar</a>
            </div>
        </form>
    </div>
    """)
    return render_template_string(html_page, active_tab='servicos')

@app.route('/servicos/excluir/<int:id>')
def excluir_servico(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM servicos_cadastrados WHERE id = %s" if DATABASE_URL else "DELETE FROM servicos_cadastrados WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Serviço excluído com sucesso!", "success")
    return redirect(url_for('servicos'))

@app.route('/pecas', methods=['GET', 'POST'])
def pecas():
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        nome = request.form['nome_peca']
        codigo = request.form['codigo']
        qtd = int(request.form['quantidade'] or 1)
        custo = float(request.form['valor_custo'] or 0)
        venda = float(request.form['valor_venda'] or 0)
        cursor.execute("INSERT INTO pecas_estoque (nome_peca, codigo, quantidade, valor_custo, valor_venda) VALUES (%s, %s, %s, %s, %s)" if DATABASE_URL else "INSERT INTO pecas_estoque (nome_peca, codigo, quantidade, valor_custo, valor_venda) VALUES (?, ?, ?, ?, ?)",
                   (nome, codigo, qtd, custo, venda))
        conn.commit()
        conn.close()
        flash("Peça cadastrada no estoque!", "success")
        return redirect(url_for('pecas'))
    cursor.execute("SELECT * FROM pecas_estoque")
    lista = cursor.fetchall()
    conn.close()

    linhas_pecas = "".join([
        f"<tr>"
        f"<td>{p['id']}</td>"
        f"<td>{p['nome_peca']}</td>"
        f"<td>{p['codigo'] or ''}</td>"
        f"<td>{p['quantidade']}</td>"
        f"<td>R$ {p['valor_custo']:.2f}</td>"
        f"<td>R$ {p['valor_venda']:.2f}</td>"
        f"<td>"
        f"<a href='/pecas/editar/{p['id']}' class='btn btn-sm btn-warning' title='Editar'><i class='fas fa-edit'></i></a> "
        f"<a href='/pecas/excluir/{p['id']}' class='btn btn-sm btn-danger' onclick=\"return confirm('Deseja excluir esta peça?');\" title='Excluir'><i class='fas fa-trash'></i></a>"
        f"</td>"
        f"</tr>"
        for p in lista
    ]) if lista else "<tr><td colspan='7' class='text-center text-muted'>Nenhuma peça no estoque.</td></tr>"

    html_page = BASE_TEMPLATE.replace("{% block content %}{% endblock %}", f"""
    <div class="header-custom"><h2><i class="fas fa-boxes"></i> Peças / Estoque</h2></div>
    <div class="card p-4 mb-4">
        <form method="POST" class="row g-3">
            <div class="col-md-4"><input type="text" class="form-control" name="nome_peca" placeholder="Nome da Peça" required></div>
            <div class="col-md-3"><input type="text" class="form-control" name="codigo" placeholder="Código / Ref"></div>
            <div class="col-md-2"><input type="number" class="form-control" name="quantidade" value="1" placeholder="Qtd"></div>
            <div class="col-md-3"><input type="number" step="0.01" class="form-control" name="valor_custo" placeholder="Custo (R$)"></div>
            <div class="col-md-3"><input type="number" step="0.01" class="form-control" name="valor_venda" placeholder="Venda (R$)"></div>
            <div class="col-md-3"><button type="submit" class="btn btn-primary w-100"><i class="fas fa-save"></i> Salvar Peça</button></div>
        </form>
    </div>
    <div class="card p-3">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h4 class="mb-0">Estoque de Peças</h4>
            <div style="width: 300px;">
                <input type="text" id="filtroPecas" class="form-control form-control-sm" placeholder="🔍 Filtrar peças..." onkeyup="filtrarTabela('filtroPecas', 'tabelaPecas')">
            </div>
        </div>
        <div class="table-responsive">
            <table id="tabelaPecas" class="table table-striped align-middle">
                <thead class="table-dark"><tr><th>ID</th><th>Peça</th><th>Código</th><th>Qtd</th><th>Custo</th><th>Venda</th><th>Ações</th></tr></thead>
                <tbody>
                    {linhas_pecas}
                </tbody>
            </table>
        </div>
    </div>
    """)
    return render_template_string(html_page, active_tab='pecas', lista=lista)

@app.route('/pecas/editar/<int:id>', methods=['GET', 'POST'])
def editar_peca(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pecas_estoque WHERE id = %s" if DATABASE_URL else "SELECT * FROM pecas_estoque WHERE id = ?", (id,))
    p = cursor.fetchone()
    
    if request.method == 'POST':
        nome = request.form['nome_peca']
        codigo = request.form['codigo']
        qtd = int(request.form['quantidade'] or 1)
        custo = float(request.form['valor_custo'] or 0)
        venda = float(request.form['valor_venda'] or 0)
        cursor.execute("UPDATE pecas_estoque SET nome_peca = %s, codigo = %s, quantidade = %s, valor_custo = %s, valor_venda = %s WHERE id = %s" if DATABASE_URL else "UPDATE pecas_estoque SET nome_peca = ?, codigo = ?, quantidade = ?, valor_custo = ?, valor_venda = ? WHERE id = ?",
                   (nome, codigo, qtd, custo, venda, id))
        conn.commit()
        conn.close()
        flash("Peça atualizada com sucesso!", "success")
        return redirect(url_for('pecas'))

    conn.close()
    html_page = BASE_TEMPLATE.replace("{% block content %}{% endblock %}", f"""
    <div class="header-custom"><h2><i class="fas fa-edit"></i> Editar Peça (ID: {p['id']})</h2></div>
    <div class="card p-4">
        <form method="POST" class="row g-3">
            <div class="col-md-6"><label class="form-label">Nome da Peça:</label><input type="text" class="form-control" name="nome_peca" value="{p['nome_peca'] or ''}" required></div>
            <div class="col-md-6"><label class="form-label">Código / Ref:</label><input type="text" class="form-control" name="codigo" value="{p['codigo'] or ''}"></div>
            <div class="col-md-4"><label class="form-label">Quantidade:</label><input type="number" class="form-control" name="quantidade" value="{p['quantidade'] or 1}"></div>
            <div class="col-md-4"><label class="form-label">Valor Custo (R$):</label><input type="number" step="0.01" class="form-control" name="valor_custo" value="{p['valor_custo'] or 0.00}"></div>
            <div class="col-md-4"><label class="form-label">Valor Venda (R$):</label><input type="number" step="0.01" class="form-control" name="valor_venda" value="{p['valor_venda'] or 0.00}"></div>
            <div class="col-12 mt-4">
                <button type="submit" class="btn btn-primary"><i class="fas fa-save"></i> Salvar Alterações</button>
                <a href="/pecas" class="btn btn-secondary">Voltar</a>
            </div>
        </form>
    </div>
    """)
    return render_template_string(html_page, active_tab='pecas')

@app.route('/pecas/excluir/<int:id>')
def excluir_peca(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pecas_estoque WHERE id = %s" if DATABASE_URL else "DELETE FROM pecas_estoque WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Peça excluída com sucesso!", "success")
    return redirect(url_for('pecas'))

@app.route('/boletos', methods=['GET', 'POST'])
def boletos():
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        cliente = request.form['cliente']
        doc = request.form['numero_documento']
        valor = float(request.form['valor'] or 0)
        venc = request.form['data_vencimento']
        cursor.execute("INSERT INTO boletos (cliente, numero_documento, valor, data_vencimento, status) VALUES (%s, %s, %s, %s, 'Gerado (Aguardando Pagamento)')" if DATABASE_URL else "INSERT INTO boletos (cliente, numero_documento, valor, data_vencimento, status) VALUES (?, ?, ?, ?, 'Gerado (Aguardando Pagamento)')",
                   (cliente, doc, valor, venc))
        conn.commit()
        conn.close()
        flash("Boleto gerado com sucesso!", "success")
        return redirect(url_for('boletos'))
    cursor.execute("SELECT * FROM boletos")
    lista = cursor.fetchall()
    conn.close()

    linhas_boletos = ""
    for b in lista:
        botao_pagar = f"<a href='/boletos/pagar/{b['id']}' class='btn btn-sm btn-success me-1' title='Marcar como Pago'><i class='fas fa-check'></i></a>" if b['status'] != 'Pago' else ''
        badge_class = 'success' if b['status'] == 'Pago' else 'warning'
        
        linhas_boletos += f"""
        <tr>
            <td>{b['id']}</td>
            <td>{b['cliente']}</td>
            <td>{b['numero_documento']}</td>
            <td>R$ {b['valor']:.2f}</td>
            <td>{b['data_vencimento']}</td>
            <td><span class='badge bg-{badge_class}'>{b['status']}</span></td>
            <td>
                {botao_pagar}
                <a href='/boletos/editar/{b['id']}' class='btn btn-sm btn-warning me-1' title='Editar'><i class='fas fa-edit'></i></a>
                <a href='/boletos/excluir/{b['id']}' class='btn btn-sm btn-danger' onclick=\"return confirm('Deseja excluir este boleto?');\" title='Excluir'><i class='fas fa-trash'></i></a>
            </td>
        </tr>
        """
    if not lista:
        linhas_boletos = "<tr><td colspan='7' class='text-center text-muted'>Nenhum boleto cadastrado.</td></tr>"

    html_page = BASE_TEMPLATE.replace("{% block content %}{% endblock %}", f"""
    <div class="header-custom"><h2><i class="fas fa-credit-card"></i> Boletos e Cobranças</h2></div>
    <div class="card p-4 mb-4">
        <form method="POST" class="row g-3">
            <div class="col-md-4"><input type="text" class="form-control" name="cliente" placeholder="Cliente" required></div>
            <div class="col-md-3"><input type="text" class="form-control" name="numero_documento" placeholder="Nº Doc / O.S." required></div>
            <div class="col-md-2"><input type="number" step="0.01" class="form-control" name="valor" placeholder="Valor (R$)" required></div>
            <div class="col-md-3"><input type="date" class="form-control" name="data_vencimento" required></div>
            <div class="col-12"><button type="submit" class="btn btn-primary"><i class="fas fa-save"></i> Lançar Boleto</button></div>
        </form>
    </div>
    <div class="card p-3">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h4 class="mb-0">Lista de Boletos</h4>
            <div style="width: 300px;">
                <input type="text" id="filtroBoletos" class="form-control form-control-sm" placeholder="🔍 Filtrar boletos..." onkeyup="filtrarTabela('filtroBoletos', 'tabelaBoletos')">
            </div>
        </div>
        <div class="table-responsive">
            <table id="tabelaBoletos" class="table table-striped align-middle">
                <thead class="table-dark"><tr><th>ID</th><th>Cliente</th><th>Nº Doc</th><th>Valor</th><th>Vencimento</th><th>Status</th><th>Ações</th></tr></thead>
                <tbody>
                    {linhas_boletos}
                </tbody>
            </table>
        </div>
    </div>
    """)
    return render_template_string(html_page, active_tab='boletos', lista=lista)

@app.route('/boletos/editar/<int:id>', methods=['GET', 'POST'])
def editar_boleto(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM boletos WHERE id = %s" if DATABASE_URL else "SELECT * FROM boletos WHERE id = ?", (id,))
    b = cursor.fetchone()
    
    if request.method == 'POST':
        cliente = request.form['cliente']
        doc = request.form['numero_documento']
        valor = float(request.form['valor'] or 0)
        venc = request.form['data_vencimento']
        status = request.form['status']
        cursor.execute("UPDATE boletos SET cliente = %s, numero_documento = %s, valor = %s, data_vencimento = %s, status = %s WHERE id = %s" if DATABASE_URL else "UPDATE boletos SET cliente = ?, numero_documento = ?, valor = ?, data_vencimento = ?, status = ? WHERE id = ?",
                   (cliente, doc, valor, venc, status, id))
        conn.commit()
        conn.close()
        flash("Boleto atualizado com sucesso!", "success")
        return redirect(url_for('boletos'))

    conn.close()
    
    sel_pend = 'selected' if b['status'] == 'Gerado (Aguardando Pagamento)' else ''
    sel_pago = 'selected' if b['status'] == 'Pago' else ''

    html_page = BASE_TEMPLATE.replace("{% block content %}{% endblock %}", f"""
    <div class="header-custom"><h2><i class="fas fa-edit"></i> Editar Boleto (ID: {b['id']})</h2></div>
    <div class="card p-4">
        <form method="POST" class="row g-3">
            <div class="col-md-6"><label class="form-label">Cliente:</label><input type="text" class="form-control" name="cliente" value="{b['cliente'] or ''}" required></div>
            <div class="col-md-6"><label class="form-label">Nº Doc / O.S.:</label><input type="text" class="form-control" name="numero_documento" value="{b['numero_documento'] or ''}" required></div>
            <div class="col-md-4"><label class="form-label">Valor (R$):</label><input type="number" step="0.01" class="form-control" name="valor" value="{b['valor'] or 0.00}" required></div>
            <div class="col-md-4"><label class="form-label">Data Vencimento:</label><input type="date" class="form-control" name="data_vencimento" value="{b['data_vencimento'] or ''}" required></div>
            <div class="col-md-4"><label class="form-label">Status:</label>
                <select class="form-select" name="status">
                    <option value="Gerado (Aguardando Pagamento)" {sel_pend}>Gerado (Aguardando Pagamento)</option>
                    <option value="Pago" {sel_pago}>Pago</option>
                </select>
            </div>
            <div class="col-12 mt-4">
                <button type="submit" class="btn btn-primary"><i class="fas fa-save"></i> Salvar Alterações</button>
                <a href="/boletos" class="btn btn-secondary">Voltar</a>
            </div>
        </form>
    </div>
    """)
    return render_template_string(html_page, active_tab='boletos')

@app.route('/boletos/pagar/<int:id>')
def pagar_boleto(id):
    conn = get_db_connection()
    hoje = datetime.now().strftime("%Y-%m-%d")
    cursor = conn.cursor()
    cursor.execute("UPDATE boletos SET status = 'Pago', data_pagamento = %s WHERE id = %s" if DATABASE_URL else "UPDATE boletos SET status = 'Pago', data_pagamento = ? WHERE id = ?", (hoje, id))
    conn.commit()
    conn.close()
    flash("Boleto marcado como PAGO!", "success")
    return redirect(url_for('boletos'))

@app.route('/boletos/excluir/<int:id>')
def excluir_boleto(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM boletos WHERE id = %s" if DATABASE_URL else "DELETE FROM boletos WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Boleto excluído com sucesso!", "success")
    return redirect(url_for('boletos'))

@app.route('/nfs', methods=['GET', 'POST'])
def nfs():
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        num = request.form['numero_nf']
        cliente = request.form['cliente']
        valor = float(request.form['valor'] or 0)
        cursor.execute("INSERT INTO notas_fiscais (numero_nf, cliente, valor, data_emissao, status) VALUES (%s, %s, %s, %s, 'Emitida')" if DATABASE_URL else "INSERT INTO notas_fiscais (numero_nf, cliente, valor, data_emissao, status) VALUES (?, ?, ?, ?, 'Emitida')",
                   (num, cliente, valor, datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
        conn.close()
        flash("Nota Fiscal registrada!", "success")
        return redirect(url_for('nfs'))
    cursor.execute("SELECT * FROM notas_fiscais")
    lista = cursor.fetchall()
    conn.close()

    linhas_nfs = "".join([
        f"<tr>"
        f"<td>{n['id']}</td>"
        f"<td>{n['numero_nf']}</td>"
        f"<td>{n['cliente']}</td>"
        f"<td>R$ {n['valor']:.2f}</td>"
        f"<td>{n['data_emissao']}</td>"
        f"<td><span class='badge bg-success'>{n['status']}</span></td>"
        f"<td>"
        f"<a href='/nfs/editar/{n['id']}' class='btn btn-sm btn-warning me-1' title='Editar'><i class='fas fa-edit'></i></a> "
        f"<a href='/nfs/excluir/{n['id']}' class='btn btn-sm btn-danger' onclick=\"return confirm('Deseja excluir esta Nota Fiscal?');\" title='Excluir'><i class='fas fa-trash'></i></a>"
        f"</td>"
        f"</tr>"
        for n in lista
    ]) if lista else "<tr><td colspan='7' class='text-center text-muted'>Nenhuma Nota Fiscal emitida.</td></tr>"

    html_page = BASE_TEMPLATE.replace("{% block content %}{% endblock %}", f"""
    <div class="header-custom"><h2><i class="fas fa-receipt"></i> Notas Fiscais (NFS-e)</h2></div>
    <div class="card p-4 mb-4">
        <form method="POST" class="row g-3">
            <div class="col-md-4"><input type="text" class="form-control" name="numero_nf" placeholder="Nº Nota Fiscal" required></div>
            <div class="col-md-5"><input type="text" class="form-control" name="cliente" placeholder="Cliente / Razão Social" required></div>
            <div class="col-md-3"><input type="number" step="0.01" class="form-control" name="valor" placeholder="Valor (R$)" required></div>
            <div class="col-12"><button type="submit" class="btn btn-primary"><i class="fas fa-save"></i> Registrar NF</button></div>
        </form>
    </div>
    <div class="card p-3">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h4 class="mb-0">Notas Fiscais Emitidas</h4>
            <div style="width: 300px;">
                <input type="text" id="filtroNFs" class="form-control form-control-sm" placeholder="🔍 Filtrar notas fiscais..." onkeyup="filtrarTabela('filtroNFs', 'tabelaNFs')">
            </div>
        </div>
        <div class="table-responsive">
            <table id="tabelaNFs" class="table table-striped align-middle">
                <thead class="table-dark"><tr><th>ID</th><th>Nº NF</th><th>Cliente</th><th>Valor</th><th>Emissão</th><th>Status</th><th>Ações</th></tr></thead>
                <tbody>
                    {linhas_nfs}
                </tbody>
            </table>
        </div>
    </div>
    """)
    return render_template_string(html_page, active_tab='nfs', lista=lista)

@app.route('/nfs/editar/<int:id>', methods=['GET', 'POST'])
def editar_nf(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notas_fiscais WHERE id = %s" if DATABASE_URL else "SELECT * FROM notas_fiscais WHERE id = ?", (id,))
    n = cursor.fetchone()
    
    if request.method == 'POST':
        num = request.form['numero_nf']
        cliente = request.form['cliente']
        valor = float(request.form['valor'] or 0)
        status = request.form['status']
        cursor.execute("UPDATE notas_fiscais SET numero_nf = %s, cliente = %s, valor = %s, status = %s WHERE id = %s" if DATABASE_URL else "UPDATE notas_fiscais SET numero_nf = ?, cliente = ?, valor = ?, status = ? WHERE id = ?",
                   (num, cliente, valor, status, id))
        conn.commit()
        conn.close()
        flash("Nota Fiscal atualizada com sucesso!", "success")
        return redirect(url_for('nfs'))

    conn.close()
    
    sel_emitida = 'selected' if n['status'] == 'Emitida' else ''
    sel_cancelada = 'selected' if n['status'] == 'Cancelada' else ''

    html_page = BASE_TEMPLATE.replace("{% block content %}{% endblock %}", f"""
    <div class="header-custom"><h2><i class="fas fa-edit"></i> Editar Nota Fiscal (ID: {n['id']})</h2></div>
    <div class="card p-4">
        <form method="POST" class="row g-3">
            <div class="col-md-6"><label class="form-label">Nº Nota Fiscal:</label><input type="text" class="form-control" name="numero_nf" value="{n['numero_nf'] or ''}" required></div>
            <div class="col-md-6"><label class="form-label">Cliente / Razão Social:</label><input type="text" class="form-control" name="cliente" value="{n['cliente'] or ''}" required></div>
            <div class="col-md-6"><label class="form-label">Valor (R$):</label><input type="number" step="0.01" class="form-control" name="valor" value="{n['valor'] or 0.00}" required></div>
            <div class="col-md-6"><label class="form-label">Status:</label>
                <select class="form-select" name="status">
                    <option value="Emitida" {sel_emitida}>Emitida</option>
                    <option value="Cancelada" {sel_cancelada}>Cancelada</option>
                </select>
            </div>
            <div class="col-12 mt-4">
                <button type="submit" class="btn btn-primary"><i class="fas fa-save"></i> Salvar Alterações</button>
                <a href="/nfs" class="btn btn-secondary">Voltar</a>
            </div>
        </form>
    </div>
    """)
    return render_template_string(html_page, active_tab='nfs')

@app.route('/nfs/excluir/<int:id>')
def excluir_nf(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notas_fiscais WHERE id = %s" if DATABASE_URL else "DELETE FROM notas_fiscais WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Nota Fiscal excluída com sucesso!", "success")
    return redirect(url_for('nfs'))

@app.route('/despesas', methods=['GET', 'POST'])
def despesas():
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        desc = request.form['descricao']
        cat = request.form['categoria']
        valor = float(request.form['valor'] or 0)
        cursor.execute("INSERT INTO despesas (descricao, categoria, valor, data_despesa) VALUES (%s, %s, %s, %s)" if DATABASE_URL else "INSERT INTO despesas (descricao, categoria, valor, data_despesa) VALUES (?, ?, ?, ?)",
                   (desc, cat, valor, datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
        conn.close()
        flash("Despesa registrada com sucesso!", "success")
        return redirect(url_for('despesas'))
    cursor.execute("SELECT * FROM despesas ORDER BY data_despesa DESC")
    lista = cursor.fetchall()
    conn.close()

    linhas_despesas = "".join([
        f"<tr>"
        f"<td>{d['id']}</td>"
        f"<td>{d['descricao']}</td>"
        f"<td>{d['categoria']}</td>"
        f"<td class='text-danger'>R$ {d['valor']:.2f}</td>"
        f"<td>{d['data_despesa']}</td>"
        f"<td>"
        f"<a href='/despesas/editar/{d['id']}' class='btn btn-sm btn-warning me-1' title='Editar'><i class='fas fa-edit'></i></a> "
        f"<a href='/despesas/excluir/{d['id']}' class='btn btn-sm btn-danger' onclick=\"return confirm('Deseja excluir esta despesa?');\" title='Excluir'><i class='fas fa-trash'></i></a>"
        f"</td>"
        f"</tr>"
        for d in lista
    ]) if lista else "<tr><td colspan='6' class='text-center text-muted'>Nenhuma despesa registrada.</td></tr>"

    html_page = BASE_TEMPLATE.replace("{% block content %}{% endblock %}", f"""
    <div class="header-custom"><h2><i class="fas fa-chart-line text-danger"></i> Despesas da Empresa</h2></div>
    <div class="card p-4 mb-4">
        <form method="POST" class="row g-3">
            <div class="col-md-4"><input type="text" class="form-control" name="descricao" placeholder="Descrição da Despesa" required></div>
            <div class="col-md-4">
                <select class="form-select" name="categoria">
                    <option value="Peças/Estoque">Peças/Estoque</option>
                    <option value="Impostos/Taxas">Impostos/Taxas</option>
                    <option value="Internet/Telefone">Internet/Telefone</option>
                    <option value="Combustível/Transporte">Combustível/Transporte</option>
                    <option value="Outros">Outros</option>
                </select>
            </div>
            <div class="col-md-4"><input type="number" step="0.01" class="form-control" name="valor" placeholder="Valor (R$)" required></div>
            <div class="col-12"><button type="submit" class="btn btn-danger"><i class="fas fa-save"></i> Salvar Despesa</button></div>
        </form>
    </div>
    <div class="card p-3">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h4 class="mb-0">Lista de Despesas</h4>
            <div style="width: 300px;">
                <input type="text" id="filtroDespesas" class="form-control form-control-sm" placeholder="🔍 Filtrar despesas..." onkeyup="filtrarTabela('filtroDespesas', 'tabelaDespesas')">
            </div>
        </div>
        <div class="table-responsive">
            <table id="tabelaDespesas" class="table table-striped align-middle">
                <thead class="table-dark"><tr><th>ID</th><th>Descrição</th><th>Categoria</th><th>Valor</th><th>Data</th><th>Ações</th></tr></thead>
                <tbody>
                    {linhas_despesas}
                </tbody>
            </table>
        </div>
    </div>
    """)
    return render_template_string(html_page, active_tab='despesas', lista=lista)

@app.route('/despesas/editar/<int:id>', methods=['GET', 'POST'])
def editar_despesa(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM despesas WHERE id = %s" if DATABASE_URL else "SELECT * FROM despesas WHERE id = ?", (id,))
    d = cursor.fetchone()
    
    if request.method == 'POST':
        desc = request.form['descricao']
        cat = request.form['categoria']
        valor = float(request.form['valor'] or 0)
        cursor.execute("UPDATE despesas SET descricao = %s, categoria = %s, valor = %s WHERE id = %s" if DATABASE_URL else "UPDATE despesas SET descricao = ?, categoria = ?, valor = ? WHERE id = ?",
                   (desc, cat, valor, id))
        conn.commit()
        conn.close()
        flash("Despesa atualizada com sucesso!", "success")
        return redirect(url_for('despesas'))

    conn.close()
    
    cat_pecas = 'selected' if d['categoria'] == 'Peças/Estoque' else ''
    cat_impostos = 'selected' if d['categoria'] == 'Impostos/Taxas' else ''
    cat_internet = 'selected' if d['categoria'] == 'Internet/Telefone' else ''
    cat_combustivel = 'selected' if d['categoria'] == 'Combustível/Transporte' else ''
    cat_outros = 'selected' if d['categoria'] == 'Outros' else ''

    html_page = BASE_TEMPLATE.replace("{% block content %}{% endblock %}", f"""
    <div class="header-custom"><h2><i class="fas fa-edit"></i> Editar Despesa (ID: {d['id']})</h2></div>
    <div class="card p-4">
        <form method="POST" class="row g-3">
            <div class="col-md-6"><label class="form-label">Descrição:</label><input type="text" class="form-control" name="descricao" value="{d['descricao'] or ''}" required></div>
            <div class="col-md-6"><label class="form-label">Categoria:</label>
                <select class="form-select" name="categoria">
                    <option value="Peças/Estoque" {cat_pecas}>Peças/Estoque</option>
                    <option value="Impostos/Taxas" {cat_impostos}>Impostos/Taxas</option>
                    <option value="Internet/Telefone" {cat_internet}>Internet/Telefone</option>
                    <option value="Combustível/Transporte" {cat_combustivel}>Combustível/Transporte</option>
                    <option value="Outros" {cat_outros}>Outros</option>
                </select>
            </div>
            <div class="col-md-6"><label class="form-label">Valor (R$):</label><input type="number" step="0.01" class="form-control" name="valor" value="{d['valor'] or 0.00}" required></div>
            <div class="col-12 mt-4">
                <button type="submit" class="btn btn-primary"><i class="fas fa-save"></i> Salvar Alterações</button>
                <a href="/despesas" class="btn btn-secondary">Voltar</a>
            </div>
        </form>
    </div>
    """)
    return render_template_string(html_page, active_tab='despesas')

@app.route('/despesas/excluir/<int:id>')
def excluir_despesa(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM despesas WHERE id = %s" if DATABASE_URL else "DELETE FROM despesas WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Despesa excluída com sucesso!", "success")
    return redirect(url_for('despesas'))

@app.route('/financeiro')
def financeiro():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    cliente_filtro = request.args.get('cliente', '')
    servico_filtro = request.args.get('servico', '')

    cursor.execute("SELECT DISTINCT cliente FROM ordens_servico WHERE cliente IS NOT NULL AND cliente != '' ORDER BY cliente")
    clientes_disponiveis = cursor.fetchall()
    cursor.execute("SELECT DISTINCT servico FROM ordens_servico WHERE servico IS NOT NULL AND servico != '' ORDER BY servico")
    servicos_disponiveis = cursor.fetchall()

    query_os = "SELECT * FROM ordens_servico WHERE 1=1"
    params_os = []
    placeholder = "%s" if DATABASE_URL else "?"
    if data_inicio:
        query_os += f" AND data_abertura >= {placeholder}"
        params_os.append(data_inicio)
    if data_fim:
        query_os += f" AND data_abertura <= {placeholder}"
        params_os.append(data_fim)
    if cliente_filtro:
        query_os += f" AND cliente = {placeholder}"
        params_os.append(cliente_filtro)
    if servico_filtro:
        query_os += f" AND servico = {placeholder}"
        params_os.append(servico_filtro)
    
    cursor.execute(query_os, params_os)
    os_filtradas = cursor.fetchall()

    query_esp = "SELECT * FROM despesas WHERE 1=1"
    params_esp = []
    if data_inicio:
        query_esp += f" AND data_despesa >= {placeholder}"
        params_esp.append(data_inicio)
    if data_fim:
        query_esp += f" AND data_despesa <= {placeholder}"
        params_esp.append(data_fim)
    
    cursor.execute(query_esp, params_esp)
    despesas_filtradas = cursor.fetchall()

    query_bol = "SELECT SUM(valor) FROM boletos WHERE status = 'Pago'"
    params_bol = []
    if data_inicio:
        query_bol += f" AND data_pagamento >= {placeholder}"
        params_bol.append(data_inicio)
    if data_fim:
        query_bol += f" AND data_pagamento <= {placeholder}"
        params_bol.append(data_fim)
    if cliente_filtro:
        query_bol += f" AND cliente = {placeholder}"
        params_bol.append(cliente_filtro)
    cursor.execute(query_bol, params_bol)
    tot_pago = cursor.fetchone()[0] or 0.0

    query_rec = "SELECT SUM(valor) FROM boletos WHERE status != 'Pago'"
    params_rec = []
    if cliente_filtro:
        query_rec += f" AND cliente = {placeholder}"
        params_rec.append(cliente_filtro)
    cursor.execute(query_rec, params_rec)
    tot_receber = cursor.fetchone()[0] or 0.0

    tot_despesas = sum([d['valor'] for d in despesas_filtradas])
    saldo = tot_pago - tot_despesas

    cursor.execute("""
        SELECT cliente, SUM(valor) as total_receita 
        FROM ordens_servico 
        WHERE cliente IS NOT NULL AND cliente != ''
        GROUP BY cliente 
        ORDER BY total_receita DESC LIMIT 5
    """)
    ranking_clientes = cursor.fetchall()

    cursor.execute("""
        SELECT servico, SUM(valor) as total_receita, COUNT(*) as qtd
        FROM ordens_servico 
        WHERE servico IS NOT NULL AND servico != ''
        GROUP BY servico 
        ORDER BY total_receita DESC LIMIT 5
    """)
    ranking_servicos = cursor.fetchall()

    cursor.execute("""
        SELECT categoria, SUM(valor) as total_despesa
        FROM despesas
        GROUP BY categoria
        ORDER BY total_despesa DESC LIMIT 5
    """)
    ranking_despesas = cursor.fetchall()

    conn.close()

    opt_clientes = "".join([f"<option value='{c['cliente']}' {'selected' if cliente_filtro == c['cliente'] else ''}>{c['cliente']}</option>" for c in clientes_disponiveis])
    opt_servicos = "".join([f"<option value='{s['servico']}' {'selected' if servico_filtro == s['servico'] else ''}>{s['servico']}</option>" for s in servicos_disponiveis])

    linhas_ranking_clientes = "".join([f"<tr><td>{c['cliente']}</td><td class='text-end fw-bold text-primary'>R$ {c['total_receita']:.2f}</td></tr>" for c in ranking_clientes]) if ranking_clientes else "<tr><td colspan='2' class='text-center text-muted'>Sem dados</td></tr>"
    linhas_ranking_servicos = "".join([f"<tr><td>{s['servico']} <small class='text-muted'>({s['qtd']}x)</small></td><td class='text-end fw-bold text-success'>R$ {s['total_receita']:.2f}</td></tr>" for s in ranking_servicos]) if ranking_servicos else "<tr><td colspan='2' class='text-center text-muted'>Sem dados</td></tr>"
    linhas_ranking_despesas = "".join([f"<tr><td>{d['categoria']}</td><td class='text-end fw-bold text-danger'>R$ {d['total_despesa']:.2f}</td></tr>" for d in ranking_despesas]) if ranking_despesas else "<tr><td colspan='2' class='text-center text-muted'>Sem dados</td></tr>"

    html_page = BASE_TEMPLATE.replace("{% block content %}{% endblock %}", f"""
    <div class="header-custom">
        <h2><i class="fas fa-chart-pie text-success"></i> Painel Financeiro & Métricas Dinâmicas</h2>
        <p class="mb-0">Filtre por período, clientes e serviços, e analise gráficos e rankings em tempo real.</p>
    </div>

    <div class="card p-3 mb-4 bg-light">
        <form method="GET" action="/financeiro" class="row g-3 align-items-end">
            <div class="col-md-2">
                <label class="form-label small fw-bold">Data Início:</label>
                <input type="date" class="form-control form-control-sm" name="data_inicio" value="{data_inicio}">
            </div>
            <div class="col-md-2">
                <label class="form-label small fw-bold">Data Fim:</label>
                <input type="date" class="form-control form-control-sm" name="data_fim" value="{data_fim}">
            </div>
            <div class="col-md-3">
                <label class="form-label small fw-bold">Cliente:</label>
                <select class="form-select form-select-sm" name="cliente">
                    <option value="">-- Todos os Clientes --</option>
                    {opt_clientes}
                </select>
            </div>
            <div class="col-md-3">
                <label class="form-label small fw-bold">Serviço:</label>
                <select class="form-select form-select-sm" name="servico">
                    <option value="">-- Todos os Serviços --</option>
                    {opt_servicos}
                </select>
            </div>
            <div class="col-md-2">
                <button type="submit" class="btn btn-primary btn-sm w-100"><i class="fas fa-filter"></i> Filtrar</button>
            </div>
        </form>
    </div>

    <div class="row g-4 mb-4">
        <div class="col-md-3">
            <div class="card p-3 text-center bg-white border-primary border-top border-4">
                <h6 class="text-muted">Receitas (Pagas)</h6>
                <h3 class="text-primary mb-0">R$ {tot_pago:.2f}</h3>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card p-3 text-center bg-white border-warning border-top border-4">
                <h6 class="text-muted">A Receber</h6>
                <h3 class="text-warning mb-0">R$ {tot_receber:.2f}</h3>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card p-3 text-center bg-white border-danger border-top border-4">
                <h6 class="text-muted">Despesas</h6>
                <h3 class="text-danger mb-0">R$ {tot_despesas:.2f}</h3>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card p-3 text-center bg-white border-success border-top border-4">
                <h6 class="text-muted">Saldo Líquido</h6>
                <h3 class="text-{'success' if saldo >= 0 else 'danger'} mb-0">R$ {saldo:.2f}</h3>
            </div>
        </div>
    </div>

    <div class="card p-4 mb-4">
        <h5 class="mb-3"><i class="fas fa-chart-bar text-primary"></i> Comparativo Dinâmico (Receitas vs Despesas)</h5>
        <div style="height: 320px; position: relative;">
            <canvas id="graficoFinanceiro"></canvas>
        </div>
    </div>

    <div class="row g-4">
        <div class="col-md-4">
            <div class="card p-3 h-100">
                <h5 class="text-primary border-bottom pb-2"><i class="fas fa-trophy"></i> Top Clientes (Receita)</h5>
                <div class="table-responsive">
                    <table class="table table-sm table-hover align-middle mb-0">
                        <thead class="table-light"><tr><th>Cliente</th><th class="text-end">Receita</th></tr></thead>
                        <tbody>
                            {linhas_ranking_clientes}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card p-3 h-100">
                <h5 class="text-success border-bottom pb-2"><i class="fas fa-award"></i> Top Serviços (Receita)</h5>
                <div class="table-responsive">
                    <table class="table table-sm table-hover align-middle mb-0">
                        <thead class="table-light"><tr><th>Serviço</th><th class="text-end">Receita</th></tr></thead>
                        <tbody>
                            {linhas_ranking_servicos}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card p-3 h-100">
                <h5 class="text-danger border-bottom pb-2"><i class="fas fa-fire"></i> Maiores Despesas (Categorias)</h5>
                <div class="table-responsive">
                    <table class="table table-sm table-hover align-middle mb-0">
                        <thead class="table-light"><tr><th>Categoria</th><th class="text-end">Total</th></tr></thead>
                        <tbody>
                            {linhas_ranking_despesas}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('graficoFinanceiro').getContext('2d');
        const graficoFinanceiro = new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: ['Receitas Pagas', 'A Receber', 'Despesas', 'Saldo Líquido'],
                datasets: [{{
                    label: 'Valores em R$',
                    data: [{tot_pago}, {tot_receber}, {tot_despesas}, {saldo}],
                    backgroundColor: [
                        'rgba(13, 110, 253, 0.7)',
                        'rgba(255, 193, 7, 0.7)',
                        'rgba(220, 53, 69, 0.7)',
                        'rgba(25, 135, 84, 0.7)'
                    ],
                    borderColor: [
                        'rgb(13, 110, 253)',
                        'rgb(255, 193, 7)',
                        'rgb(220, 53, 69)',
                        'rgb(25, 135, 84)'
                    ],
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{
                        beginAtZero: true
                    }}
                }}
            }}
        }});
    </script>
    """)
    return render_template_string(html_page, active_tab='financeiro')

if __name__ == '__main__':
    app.run(debug=True, port=5000)