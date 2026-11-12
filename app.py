from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify
import sqlite3
import os
import json
from datetime import datetime
import urllib.parse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

app = Flask(__name__)
app.secret_key = 'clinica_hardware_secret_key'

# --- CONFIGURAÇÕES DE E-MAIL (GMAIL) ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "hardwareclinica@gmail.com"
SMTP_PASSWORD = "qxyj lgfq marr sddo"  # Sua senha de app configurada

def enviar_email_com_anexo_smtp(destinatario, assunto, corpo_html, pdf_bytes, nome_arquivo_pdf):
    if not destinatario:
        return False, "E-mail do cliente não informado."
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = destinatario
        msg['Subject'] = assunto

        # Corpo HTML do e-mail
        msg.attach(MIMEText(corpo_html, 'html', 'utf-8'))

        # Anexo PDF
        if pdf_bytes:
            parte_anexo = MIMEApplication(pdf_bytes, Name=nome_arquivo_pdf)
            parte_anexo['Content-Disposition'] = f'attachment; filename="{nome_arquivo_pdf}"'
            msg.attach(parte_anexo)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, destinatario, msg.as_string())
        server.quit()
        return True, "E-mail com anexo enviado com sucesso!"
    except Exception as e:
        return False, str(e)

def get_db_connection():
    conn = sqlite3.connect("clinica_do_hardware.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            nome TEXT, cpf_cnpj TEXT, contato TEXT, email TEXT, 
            cep TEXT, rua TEXT, numero TEXT, bairro TEXT, complemento TEXT, cidade_uf TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS servicos_cadastrados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_servico TEXT, descricao TEXT, valor_padrao REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pecas_estoque (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_peca TEXT, codigo TEXT, quantidade INTEGER, valor_custo REAL, valor_venda REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ordem_entrada (
            id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, cpf_cnpj TEXT, contato TEXT, email TEXT,
            tipo_equip TEXT, marca TEXT, equipamento TEXT, ns_patrimonio TEXT,
            acessorios TEXT, condicao TEXT, defeito TEXT, data_entrada TEXT
        )
    """)
    try:
        cursor.execute("ALTER TABLE ordem_entrada ADD COLUMN marca TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE ordem_entrada ADD COLUMN email TEXT")
    except sqlite3.OperationalError:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ordens_servico (
            id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, cpf_cnpj TEXT, contato TEXT,
            email_end TEXT, tipo_equip TEXT, equipamento TEXT, marca TEXT, ns_patrimonio TEXT,
            acessorios TEXT, condicao TEXT, status TEXT DEFAULT 'Aguardando Aprovação',
            defeito TEXT, diagnostico TEXT, servico TEXT, servicos_json TEXT, peca_utilizada TEXT, pecas_json TEXT, valor_pecas REAL, valor_servico REAL, 
            valor REAL, foto_equip TEXT, data_abertura TEXT
        )
    """)
    try:
        cursor.execute("ALTER TABLE ordens_servico ADD COLUMN pecas_json TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE ordens_servico ADD COLUMN servicos_json TEXT")
    except sqlite3.OperationalError:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS boletos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, numero_documento TEXT,
            valor REAL, data_vencimento TEXT, data_pagamento TEXT, 
            status TEXT DEFAULT 'Gerado (Aguardando Pagamento)'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notas_fiscais (
            id INTEGER PRIMARY KEY AUTOINCREMENT, numero_nf TEXT, cliente TEXT,
            valor REAL, data_emissao TEXT, status TEXT DEFAULT 'Emitida'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS despesas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, descricao TEXT, categoria TEXT,
            valor REAL, data_despesa TEXT, comprovante TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Clínica do Hardware - ERP Integrado</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background-color: #f8f9fa; }
        .navbar-brand { font-weight: bold; color: #fff !important; }
        .header-custom { background-color: #002060; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .card { box-shadow: 0 4px 6px rgba(0,0.1,0,0.1); border: none; }
    </style>
    <script>
        function consultarCep(cepInputId, ruaId, bairroId, cidadeUfId) {
            let cep = document.getElementById(cepInputId).value.replace(/\\D/g, '');
            if (cep.length === 8) {
                fetch(`https://viacep.com.br/ws/${cep}/json/`)
                    .then(response => response.json())
                    .then(data => {
                        if (!data.erro) {
                            if(document.getElementById(ruaId)) document.getElementById(ruaId).value = data.logradouro;
                            if(document.getElementById(bairroId)) document.getElementById(bairroId).value = data.bairro;
                            if(document.getElementById(cidadeUfId)) document.getElementById(cidadeUfId).value = data.localidade + ' / ' + data.uf;
                        } else {
                            alert("CEP não encontrado.");
                        }
                    }).catch(err => console.log("Erro ao buscar CEP:", err));
            }
        }

        function consultarCnpjCompleto(cnpjInputId, nomeId, contatoId, emailId = null, cepId = null, ruaId = null, numId = null, bairroId = null, complId = null, cidadeId = null) {
            let cnpj = document.getElementById(cnpjInputId).value.replace(/\\D/g, '');
            if (cnpj.length === 14) {
                fetch(`https://brasilapi.com.br/api/cnpj/v1/${cnpj}`)
                    .then(response => response.json())
                    .then(data => {
                        if (!data.message) {
                            if(document.getElementById(nomeId)) document.getElementById(nomeId).value = data.razao_social || data.nome_fantasia || '';
                            if(contatoId && document.getElementById(contatoId)) document.getElementById(contatoId).value = data.ddd_telefone_1 ? `(${data.ddd_telefone_1.slice(0,2)}) ${data.ddd_telefone_1.slice(2)}` : '';
                            if(emailId && document.getElementById(emailId)) document.getElementById(emailId).value = data.email || '';
                            if(cepId && document.getElementById(cepId)) document.getElementById(cepId).value = data.cep ? data.cep.replace(/\\D/g, '') : '';
                            if(ruaId && document.getElementById(ruaId)) document.getElementById(ruaId).value = data.logradouro || '';
                            if(numId && document.getElementById(numId)) document.getElementById(numId).value = data.numero || '';
                            if(bairroId && document.getElementById(bairroId)) document.getElementById(bairroId).value = data.bairro || '';
                            if(complId && document.getElementById(complId)) document.getElementById(complId).value = data.complemento || '';
                            if(cidadeId && document.getElementById(cidadeId)) document.getElementById(cidadeId).value = (data.municipio && data.uf) ? data.municipio + ' / ' + data.uf : '';
                        } else {
                            alert("CNPJ não encontrado na base de dados.");
                        }
                    }).catch(err => console.log("Erro ao buscar CNPJ:", err));
            }
        }

        function alterarStatusRapido(osId, novoStatus) {
            fetch(`/os/status_rapido/${osId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: novoStatus })
            })
            .then(response => response.json())
            .then(data => {
                if(data.sucesso) {
                    location.reload();
                } else {
                    alert("Erro ao atualizar status.");
                }
            })
            .catch(err => console.log("Erro:", err));
        }

        function selecionarClienteCadastrado(selectObj) {
            let opt = selectObj.options[selectObj.selectedIndex];
            if(opt.value) {
                document.getElementById('cliente_input').value = opt.getAttribute('data-nome') || '';
                document.getElementById('cpf_cnpj_input').value = opt.getAttribute('data-doc') || '';
                document.getElementById('contato_input').value = opt.getAttribute('data-contato') || '';
                if(document.getElementById('email_input')) {
                    document.getElementById('email_input').value = opt.getAttribute('data-email') || '';
                }
            }
        }

        let listaServicosDisponiveis = [];
        let listaPecasEstoque = [];

        function inicializarServicosDisponiveis(servicosJson) {
            listaServicosDisponiveis = servicosJson;
        }

        function inicializarPecasDisponiveis(pecasJson) {
            listaPecasEstoque = pecasJson;
        }

        function adicionarLinhaServico(servicoNome = "", qtd = 1, valorUnit = 0) {
            let container = document.getElementById('container-servicos');
            let divId = 'servico_row_' + Date.now() + Math.random().toString(36).substring(2, 5);
            
            let optionsHtml = "<option value=''>-- Selecione um serviço --</option>";
            listaServicosDisponiveis.forEach(s => {
                let sel = (s.nome_servico === servicoNome) ? "selected" : "";
                optionsHtml += `<option value="${s.nome_servico}" data-valor="${s.valor_padrao}" ${sel}>${s.nome_servico} (R$ ${s.valor_padrao.toFixed(2)})</option>`;
            });

            let htmlRow = `
                <div class="row g-2 align-items-center mb-2 servico-item-row" id="${divId}">
                    <div class="col-md-7">
                        <select class="form-select servico-select" onchange="atualizarValorServicosTotal()">
                            ${optionsHtml}
                        </select>
                    </div>
                    <div class="col-md-3">
                        <div class="input-group">
                            <span class="input-group-text small">Qtd</span>
                            <input type="number" class="form-control servico-qtd" value="${qtd}" min="1" oninput="atualizarValorServicosTotal()">
                        </div>
                    </div>
                    <div class="col-md-2">
                        <button type="button" class="btn btn-danger btn-sm w-100" onclick="removerLinhaServico('${divId}')"><i class="fas fa-trash"></i></button>
                    </div>
                </div>
            `;
            container.insertAdjacentHTML('beforeend', htmlRow);
            atualizarValorServicosTotal();
        }

        function removerLinhaServico(divId) {
            let elem = document.getElementById(divId);
            if(elem) {
                elem.remove();
                atualizarValorServicosTotal();
            }
        }

        function atualizarValorServicosTotal() {
            let rows = document.querySelectorAll('.servico-item-row');
            let totalServicos = 0;
            let servicosResumoArr = [];

            rows.forEach(row => {
                let sel = row.querySelector('.servico-select');
                let qtdInput = row.querySelector('.servico-qtd');
                if(sel && sel.value) {
                    let opt = sel.options[sel.selectedIndex];
                    let vUnit = parseFloat(opt.getAttribute('data-valor')) || 0;
                    let qtd = parseInt(qtdInput.value) || 1;
                    totalServicos += (vUnit * qtd);
                    servicosResumoArr.push({nome: sel.value, quantidade: qtd, valor_unitario: vUnit});
                }
            });

            document.getElementById('valor_servico_input').value = totalServicos.toFixed(2);
            document.getElementById('servicos_json_input').value = JSON.stringify(servicosResumoArr);
            calcularTotalOS();
        }

        function adicionarLinhaPeca(pecaNome = "", qtd = 1, valorUnit = 0) {
            let container = document.getElementById('container-pecas');
            let divId = 'peca_row_' + Date.now() + Math.random().toString(36).substring(2, 5);
            
            let optionsHtml = "<option value=''>-- Selecione uma peça --</option>";
            listaPecasEstoque.forEach(p => {
                let sel = (p.nome_peca === pecaNome) ? "selected" : "";
                let vUnit = p.valor_venda;
                optionsHtml += `<option value="${p.nome_peca}" data-valor="${vUnit}" ${sel}>${p.nome_peca} (Estq: ${p.quantidade} | R$ ${vUnit.toFixed(2)})</option>`;
            });

            let htmlRow = `
                <div class="row g-2 align-items-center mb-2 peca-item-row" id="${divId}">
                    <div class="col-md-7">
                        <select class="form-select peca-select" onchange="atualizarValorPecasTotal()">
                            ${optionsHtml}
                        </select>
                    </div>
                    <div class="col-md-3">
                        <div class="input-group">
                            <span class="input-group-text small">Qtd</span>
                            <input type="number" class="form-control peca-qtd" value="${qtd}" min="1" oninput="atualizarValorPecasTotal()">
                        </div>
                    </div>
                    <div class="col-md-2">
                        <button type="button" class="btn btn-danger btn-sm w-100" onclick="removerLinhaPeca('${divId}')"><i class="fas fa-trash"></i></button>
                    </div>
                </div>
            `;
            container.insertAdjacentHTML('beforeend', htmlRow);
            atualizarValorPecasTotal();
        }

        function removerLinhaPeca(divId) {
            let elem = document.getElementById(divId);
            if(elem) {
                elem.remove();
                atualizarValorPecasTotal();
            }
        }

        function atualizarValorPecasTotal() {
            let rows = document.querySelectorAll('.peca-item-row');
            let totalPecas = 0;
            let pecasResumoArr = [];

            rows.forEach(row => {
                let sel = row.querySelector('.peca-select');
                let qtdInput = row.querySelector('.peca-qtd');
                if(sel && sel.value) {
                    let opt = sel.options[sel.selectedIndex];
                    let vUnit = parseFloat(opt.getAttribute('data-valor')) || 0;
                    let qtd = parseInt(qtdInput.value) || 1;
                    totalPecas += (vUnit * qtd);
                    pecasResumoArr.push({nome: sel.value, quantidade: qtd, valor_unitario: vUnit});
                }
            });

            document.getElementById('valor_pecas_input').value = totalPecas.toFixed(2);
            document.getElementById('pecas_json_input').value = JSON.stringify(pecasResumoArr);
            calcularTotalOS();
        }

        function calcularTotalOS() {
            let vPecas = parseFloat(document.getElementById('valor_pecas_input').value) || 0;
            let vServico = parseFloat(document.getElementById('valor_servico_input').value) || 0;
            let total = vPecas + vServico;
            let totalField = document.getElementById('valor_total_input');
            if (totalField) {
                totalField.value = total.toFixed(2);
            }
        }

        function preencherDadosEntrada(selectObj) {
            let opt = selectObj.options[selectObj.selectedIndex];
            if(opt.value) {
                document.getElementById('cliente_field').value = opt.getAttribute('data-cliente') || '';
                document.getElementById('cpf_cnpj_field').value = opt.getAttribute('data-doc') || '';
                document.getElementById('contato_field').value = opt.getAttribute('data-contato') || '';
                if(document.getElementById('email_field')) {
                    document.getElementById('email_field').value = opt.getAttribute('data-email') || '';
                }
                document.querySelector('input[name="tipo_equip"]').value = opt.getAttribute('data-tipo') || '';
                document.querySelector('input[name="marca"]').value = opt.getAttribute('data-marca') || '';
                document.querySelector('input[name="equipamento"]').value = opt.getAttribute('data-equip') || '';
                document.querySelector('input[name="ns_patrimonio"]').value = opt.getAttribute('data-ns') || '';
                document.querySelector('input[name="acessorios"]').value = opt.getAttribute('data-acessorios') || '';
                document.querySelector('input[name="condicao"]').value = opt.getAttribute('data-condicao') || '';
                document.querySelector('textarea[name="defeito"]').value = opt.getAttribute('data-defeito') || '';
            }
        }

        function filtrarTabela(inputId, tableId) {
            let input = document.getElementById(inputId);
            let filter = input.value.toLowerCase();
            let table = document.getElementById(tableId);
            let tr = table.getElementsByTagName("tr");

            for (let i = 1; i < tr.length; i++) {
                let rowText = tr[i].textContent || tr[i].innerText;
                if (rowText.toLowerCase().indexOf(filter) > -1) {
                    tr[i].style.display = "";
                } else {
                    tr[i].style.display = "none";
                }
            }
        }

        function verificarOutroTipo(selectObj) {
            let outroDiv = document.getElementById('outro_tipo_div');
            let outroInput = document.getElementById('outro_tipo_input');
            if (selectObj.value === 'Outros') {
                outroDiv.style.display = 'block';
                outroInput.required = true;
            } else {
                outroDiv.style.display = 'none';
                outroInput.required = false;
                outroInput.value = '';
            }
        }

        function verificarOutraMarca(selectObj) {
            let outroDiv = document.getElementById('outra_marca_div');
            let outroInput = document.getElementById('outra_marca_input');
            if (selectObj.value === 'Outros') {
                outroDiv.style.display = 'block';
                outroInput.required = true;
            } else {
                outroDiv.style.display = 'none';
                outroInput.required = false;
                outroInput.value = '';
            }
        }
    </script>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark mb-4">
        <div class="container-fluid">
            <a class="navbar-brand" href="/"><i class="fas fa-laptop-medical"></i> CLÍNICA DO HARDWARE</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item"><a class="nav-link {% if active_tab == 'entrada' %}active{% endif %}" href="/entrada"><i class="fas fa-sign-in-alt text-info"></i> Entrada Equip.</a></li>
                    <li class="nav-item"><a class="nav-link {% if active_tab == 'os' %}active{% endif %}" href="/"><i class="fas fa-clipboard-list"></i> Ordens de Serviço</a></li>
                    <li class="nav-item"><a class="nav-link {% if active_tab == 'clientes' %}active{% endif %}" href="/clientes"><i class="fas fa-users"></i> Clientes</a></li>
                    <li class="nav-item"><a class="nav-link {% if active_tab == 'servicos' %}active{% endif %}" href="/servicos"><i class="fas fa-tools"></i> Serviços</a></li>
                    <li class="nav-item"><a class="nav-link {% if active_tab == 'pecas' %}active{% endif %}" href="/pecas"><i class="fas fa-boxes"></i> Peças / Estoque</a></li>
                    <li class="nav-item"><a class="nav-link {% if active_tab == 'boletos' %}active{% endif %}" href="/boletos"><i class="fas fa-credit-card"></i> Boletos</a></li>
                    <li class="nav-item"><a class="nav-link {% if active_tab == 'nfs' %}active{% endif %}" href="/nfs"><i class="fas fa-receipt"></i> Notas Fiscais</a></li>
                    <li class="nav-item"><a class="nav-link {% if active_tab == 'despesas' %}active{% endif %}" href="/despesas"><i class="fas fa-chart-line text-danger"></i> Despesas</a></li>
                    <li class="nav-item"><a class="nav-link {% if active_tab == 'financeiro' %}active{% endif %}" href="/financeiro"><i class="fas fa-chart-pie text-success"></i> Painel & Gráficos</a></li>
                </ul>
            </div>
        </div>
    </nav>

    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'success' if category == 'success' else 'danger' }} alert-dismissible fade show" role="alert">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        {% block content %}{% endblock %}
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

@app.route('/entrada', methods=['GET', 'POST'])
def ordem_entrada():
    conn = get_db_connection()
    if request.method == 'POST':
        cliente = request.form['cliente']
        cpf_cnpj = request.form['cpf_cnpj']
        contato = request.form['contato']
        email = request.form['email']
        
        tipo_equip_sel = request.form['tipo_equip']
        tipo_equip = request.form['outro_tipo'] if tipo_equip_sel == 'Outros' else tipo_equip_sel

        marca_sel = request.form['marca']
        marca = request.form['outra_marca'] if marca_sel == 'Outros' else marca_sel

        equipamento = request.form['equipamento']
        ns_patrimonio = request.form['ns_patrimonio']
        acessorios = request.form['acessorios']
        condicao = request.form['condicao']
        defeito = request.form['defeito']
        data_hoje = datetime.now().strftime("%Y-%m-%d")

        conn.execute("""INSERT INTO ordem_entrada (cliente, cpf_cnpj, contato, email, tipo_equip, marca, equipamento, ns_patrimonio, acessorios, condicao, defeito, data_entrada)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (cliente, cpf_cnpj, contato, email, tipo_equip, marca, equipamento, ns_patrimonio, acessorios, condicao, defeito, data_hoje))
        conn.commit()
        conn.close()
        flash("Entrada de equipamento registrada com sucesso!", "success")
        return redirect(url_for('ordem_entrada'))

    lista_entradas = conn.execute("SELECT * FROM ordem_entrada ORDER BY id DESC").fetchall()
    lista_clientes = conn.execute("SELECT * FROM clientes ORDER BY nome ASC").fetchall()
    conn.close()
    
    options_clientes = ""
    for c in lista_clientes:
        doc_str = f" ({c['cpf_cnpj']})" if c['cpf_cnpj'] else ""
        options_clientes += f"<option value='{c['id']}' data-nome='{c['nome']}' data-doc='{c['cpf_cnpj'] or ''}' data-contato='{c['contato'] or ''}' data-email='{c['email'] or ''}'>{c['nome']}{doc_str}</option>"

    html_page = BASE_TEMPLATE.replace("{% block content %}{% endblock %}", f"""
    <div class="header-custom">
        <h2><i class="fas fa-sign-in-alt"></i> Ordem de Entrada de Equipamentos (Check-in)</h2>
        <p class="mb-0">Registre a chegada dos aparelhos para posterior conversão em Ordem de Serviço</p>
    </div>
    
    <div class="card p-4 mb-4">
        <h4>Nova Entrada de Aparelho</h4>
        <form method="POST" class="row g-3">
            <div class="col-md-12 p-3 bg-light border rounded mb-2">
                <label class="form-label text-primary"><strong><i class="fas fa-users"></i> Selecionar Cliente Cadastrado (Opcional):</strong></label>
                <select class="form-select border-primary" onchange="selecionarClienteCadastrado(this)">
                    <option value="">-- Escolher um cliente já cadastrado ou digitar abaixo --</option>
                    {options_clientes}
                </select>
            </div>
            <div class="col-md-6">
                <label class="form-label">Nome do Cliente:</label>
                <input type="text" class="form-control" id="cliente_input" name="cliente" placeholder="Nome do Cliente" required>
            </div>
            <div class="col-md-6">
                <label class="form-label">CPF / CNPJ (Preenche tudo se CNPJ):</label>
                <input type="text" class="form-control" id="cpf_cnpj_input" name="cpf_cnpj" placeholder="Digite o CPF ou CNPJ" onblur="consultarCnpjCompleto('cpf_cnpj_input', 'cliente_input', 'contato_input', 'email_input')">
            </div>
            <div class="col-md-6">
                <label class="form-label">Contato (WhatsApp):</label>
                <input type="text" class="form-control" id="contato_input" name="contato" placeholder="Contato (WhatsApp)">
            </div>
            <div class="col-md-6">
                <label class="form-label">E-mail do Cliente:</label>
                <input type="email" class="form-control" id="email_input" name="email" placeholder="E-mail para envio">
            </div>
            <div class="col-md-6">
                <label class="form-label">Tipo de Equipamento:</label>
                <select class="form-select" id="tipo_equip_select" name="tipo_equip" onchange="verificarOutroTipo(this)" required>
                    <option value="NOTEBOOK">NOTEBOOK</option>
                    <option value="DESKTOP">DESKTOP</option>
                    <option value="ALL IN ONE">ALL IN ONE</option>
                    <option value="IMPRESSORA">IMPRESSORA</option>
                    <option value="MONITOR">MONITOR</option>
                    <option value="NO-BREAK">NO-BREAK</option>
                    <option value="SMARTPHONE">SMARTPHONE</option>
                    <option value="TABLET">TABLET</option>
                    <option value="Outros">Outros</option>
                </select>
            </div>
            <div class="col-md-6" id="outro_tipo_div" style="display: none;">
                <label class="form-label text-danger">Especifique o Tipo de Equipamento:</label>
                <input type="text" class="form-control" id="outro_tipo_input" name="outro_tipo" placeholder="Digite o tipo do equipamento">
            </div>
            <div class="col-md-6">
                <label class="form-label">Marca:</label>
                <select class="form-select" id="marca_select" name="marca" onchange="verificarOutraMarca(this)" required>
                    <option value="DELL">DELL</option>
                    <option value="LENOVO">LENOVO</option>
                    <option value="HP">HP</option>
                    <option value="ACER">ACER</option>
                    <option value="ASUS">ASUS</option>
                    <option value="SAMSUNG">SAMSUNG</option>
                    <option value="APPLE">APPLE</option>
                    <option value="POSITIVO">POSITIVO</option>
                    <option value="MULTILASER">MULTILASER</option>
                    <option value="INTELBRAS">INTELBRAS</option>
                    <option value="EPSON">EPSON</option>
                    <option value="Outros">Outros</option>
                </select>
            </div>
            <div class="col-md-6" id="outra_marca_div" style="display: none;">
                <label class="form-label text-danger">Especifique a Marca:</label>
                <input type="text" class="form-control" id="outra_marca_input" name="outra_marca" placeholder="Digite o nome da marca">
            </div>
            <div class="col-md-8">
                <label class="form-label">Modelo do Equipamento:</label>
                <input type="text" class="form-control" id="equipamento_input" name="equipamento" placeholder="Ex: Inspiron 15 / A515" required>
            </div>
            <div class="col-md-4">
                <label class="form-label">Nº de Série / Patrimônio:</label>
                <input type="text" class="form-control" id="ns_patrimonio_input" name="ns_patrimonio" placeholder="Nº de Série">
            </div>
            <div class="col-md-6">
                <label class="form-label">Acessórios Deixados:</label>
                <input type="text" class="form-control" id="acessorios_input" name="acessorios" placeholder="Ex: Carregador, Bolsa">
            </div>
            <div class="col-md-6">
                <label class="form-label">Condição Visual:</label>
                <input type="text" class="form-control" id="condicao_input" name="condicao" placeholder="Ex: Arranhões na tampa">
            </div>
            <div class="col-md-12">
                <label class="form-label">Defeito Relatado pelo Cliente:</label>
                <textarea class="form-control" id="defeito_input" name="defeito" placeholder="Defeito relatado" rows="2"></textarea>
            </div>
            <div class="col-12">
                <button type="submit" class="btn btn-info text-white"><i class="fas fa-save"></i> Registrar Entrada</button>
            </div>
        </form>
    </div>

    <div class="card p-3">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h4 class="mb-0">Equipamentos na Recepção / Aguardando Orçamento</h4>
            <div style="width: 300px;">
                <input type="text" id="filtroEntrada" class="form-control form-control-sm" placeholder="🔍 Filtrar registros..." onkeyup="filtrarTabela('filtroEntrada', 'tabelaEntrada')">
            </div>
        </div>
        <div class="table-responsive">
            <table id="tabelaEntrada" class="table table-striped table-hover align-middle">
                <thead class="table-dark">
                    <tr>
                        <th>Nº Entrada</th>
                        <th>Cliente</th>
                        <th>CPF/CNPJ</th>
                        <th>Tipo / Marca / Modelo</th>
                        <th>Defeito Relatado</th>
                        <th>Data</th>
                        <th>Ações / Envio</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join([f"<tr><td><strong>ENT-{e['id']:04d}</strong></td><td>" + str(e['cliente']) + f"</td><td>" + str(e['cpf_cnpj'] or '-') + f"</td><td><strong>" + str(e['tipo_equip']) + f"</strong> - " + str(e['marca'] or '') + f" " + str(e['equipamento']) + f"</td><td>" + str(e['defeito'] or '-') + f"</td><td>" + str(e['data_entrada']) + f"</td><td>" +
                    f"<div class='btn-group btn-group-sm mb-1'>" +
                    f"<a href='/entrada/imprimir/" + str(e['id']) + f"' class='btn btn-primary' target='_blank' title='2 Vias (Imprimir/PDF)'><i class='fas fa-print'></i> 2 Vias</a>" +
                    f"<a href='/entrada/imprimir_via_unica/" + str(e['id']) + f"' class='btn btn-outline-primary' target='_blank' title='Via Única Cliente' style='background:#e7f1ff;'><i class='fas fa-file-alt'></i> Via Única</a>" +
                    f"</div>" +
                    f"<div class='btn-group btn-group-sm'>" +
                    f"<a href='/entrada/enviar_email/" + str(e['id']) + f"' class='btn btn-warning' title='Enviar por E-mail (Gmail)'><i class='fas fa-envelope'></i></a>" +
                    f"<a href='https://api.whatsapp.com/send?phone=55" + ''.join(filter(str.isdigit, str(e['contato'] or ''))) + f"&text=" + urllib.parse.quote(f"Olá *{e['cliente']}*, seu equipamento (*{e['tipo_equip']} {e['marca'] or ''} {e['equipamento']}*) deu entrada na Clínica do Hardware sob o nº *ENT-{e['id']:04d}*. Agradecemos a confiança!") + f"' target='_blank' class='btn btn-success' title='Enviar no WhatsApp'><i class='fab fa-whatsapp'></i></a>" +
                    f"<a href='/os/nova_de_entrada/" + str(e['id']) + f"' class='btn btn-info text-white' title='Gerar O.S.'><i class='fas fa-file-invoice-dollar'></i></a>" +
                    f"<a href='/entrada/excluir/" + str(e['id']) + f"' class='btn btn-danger' onclick=\"return confirm('Excluir este registro de entrada?')\" title='Excluir'><i class='fas fa-trash'></i></a>" +
                    f"</div>" +
                    f"</td></tr>" for e in lista_entradas]) if lista_entradas else "<tr><td colspan='7' class='text-center text-muted'>Nenhum equipamento na recepção.</td></tr>"}
                </tbody>
            </table>
        </div>
    </div>
    """)
    return render_template_string(html_page, active_tab='entrada', lista=lista_entradas)

def gerar_html_comprovante_entrada(e):
    data_formatada = datetime.strptime(e['data_entrada'], "%Y-%m-%d").strftime("%d/%m/%Y") if e['data_entrada'] else ""
    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Ordem de Entrada - ENT-{e['id']:04d}</title>
        <style>
            body {{ font-family: Arial, sans-serif; font-size: 12px; color: #333; margin: 0; padding: 20px; }}
            .box {{ border: 1px solid #002060; padding: 20px; border-radius: 6px; }}
            .header {{ border-bottom: 2px solid #002060; padding-bottom: 10px; margin-bottom: 15px; display: flex; justify-content: space-between; }}
            .section-title {{ background-color: #f0f4f8; border-left: 4px solid #002060; padding: 5px 10px; font-weight: bold; margin: 15px 0 10px 0; text-transform: uppercase; color: #002060; }}
            p {{ margin: 4px 0; }}
        </style>
    </head>
    <body>
        <div class="box">
            <div class="header">
                <div>
                    <h3 style="margin:0; color:#002060;">CLÍNICA DO HARDWARE</h3>
                    <p style="margin:2px 0; font-size:10px; color:#666;">CNPJ: 70.017.290/0001-61 | Tel: (98) 9 8482-9705</p>
                </div>
                <div style="text-align: right;">
                    <h4 style="margin:0; color:#d9534f;">COMPROVANTE DE ENTRADA</h4>
                    <p style="margin:2px 0; font-weight:bold;">Nº ENT-{e['id']:04d}</p>
                    <p style="margin:2px 0; font-size:10px;">Data: {data_formatada}</p>
                </div>
            </div>
            <div class="section-title">01 Dados do Cliente</div>
            <p><strong>Cliente:</strong> {e['cliente']}</p>
            <p><strong>CPF/CNPJ:</strong> {e['cpf_cnpj'] or 'Não informado'}</p>
            <p><strong>WhatsApp:</strong> {e['contato'] or 'Não informado'}</p>

            <div class="section-title">02 Equipamento</div>
            <p><strong>Tipo:</strong> {e['tipo_equip']} | <strong>Marca:</strong> {e['marca'] or '-'} | <strong>Modelo:</strong> {e['equipamento']}</p>
            <p><strong>Nº de Série / Patrimônio:</strong> {e['ns_patrimonio'] or 'Não informado'}</p>
            <p><strong>Acessórios:</strong> {e['acessorios'] or 'Nenhum'}</p>
            <p><strong>Condição Visual:</strong> {e['condicao'] or 'Normal'}</p>

            <div class="section-title">03 Defeito Relatado</div>
            <p>{e['defeito'] or 'Não especificado'}</p>
        </div>
    </body>
    </html>
    """

def gerar_html_os(os_item):
    data_formatada = datetime.strptime(os_item['data_abertura'], "%Y-%m-%d").strftime("%d/%m/%Y") if os_item['data_abertura'] else ""
    
    itens_linhas_html = ""
    try:
        servicos_arr = json.loads(os_item['servicos_json']) if os_item['servicos_json'] else []
    except:
        servicos_arr = []

    if servicos_arr:
        for s in servicos_arr:
            subtotal = s['quantidade'] * s['valor_unitario']
            itens_linhas_html += f"<tr><td>Serviço</td><td>{s['nome']}</td><td style='text-align:center;'>{s['quantidade']}</td><td style='text-align:right;'>R$ {subtotal:.2f}</td></tr>"
    elif os_item['servico']:
        itens_linhas_html += f"<tr><td>Serviço</td><td>{os_item['servico']}</td><td style='text-align:center;'>1</td><td style='text-align:right;'>R$ {(os_item['valor_servico'] or 0.0):.2f}</td></tr>"

    try:
        pecas_arr = json.loads(os_item['pecas_json']) if os_item['pecas_json'] else []
    except:
        pecas_arr = []

    if pecas_arr:
        for p in pecas_arr:
            subtotal = p['quantidade'] * p['valor_unitario']
            itens_linhas_html += f"<tr><td>Peça</td><td>{p['nome']}</td><td style='text-align:center;'>{p['quantidade']}</td><td style='text-align:right;'>R$ {subtotal:.2f}</td></tr>"
    elif os_item['peca_utilizada']:
        itens_linhas_html += f"<tr><td>Peça</td><td>{os_item['peca_utilizada']}</td><td style='text-align:center;'>1</td><td style='text-align:right;'>R$ {(os_item['valor_pecas'] or 0.0):.2f}</td></tr>"

    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Ordem de Serviço - OS-{os_item['id']:04d}</title>
        <style>
            body {{ font-family: Arial, sans-serif; font-size: 12px; color: #333; margin: 0; padding: 20px; }}
            .box {{ border: 1px solid #002060; padding: 20px; border-radius: 6px; }}
            .header {{ border-bottom: 2px solid #002060; padding-bottom: 10px; margin-bottom: 15px; display: flex; justify-content: space-between; }}
            .section-title {{ background-color: #f0f4f8; border-left: 4px solid #002060; padding: 5px 10px; font-weight: bold; margin: 15px 0 10px 0; text-transform: uppercase; color: #002060; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ border: 1px solid #ddd; padding: 6px 8px; font-size: 11px; }}
            th {{ background-color: #002060; color: white; }}
            p {{ margin: 4px 0; }}
        </style>
    </head>
    <body>
        <div class="box">
            <div class="header">
                <div>
                    <h3 style="margin:0; color:#002060;">CLÍNICA DO HARDWARE</h3>
                    <p style="margin:2px 0; font-size:10px; color:#666;">CNPJ: 70.017.290/0001-61 | Tel: (98) 9 8482-9705</p>
                </div>
                <div style="text-align: right;">
                    <h4 style="margin:0; color:#d9534f;">ORDEM DE SERVIÇO</h4>
                    <p style="margin:2px 0; font-weight:bold;">Nº OS-{os_item['id']:04d}</p>
                    <p style="margin:2px 0; font-size:10px;">Data: {data_formatada} | Status: {os_item['status']}</p>
                </div>
            </div>
            <div class="section-title">01 Dados do Cliente</div>
            <p><strong>Cliente:</strong> {os_item['cliente']}</p>
            <p><strong>CPF/CNPJ:</strong> {os_item['cpf_cnpj'] or 'Não informado'}</p>
            <p><strong>Contato:</strong> {os_item['contato'] or 'Não informado'} | <strong>E-mail:</strong> {os_item['email_end'] or 'Não informado'}</p>

            <div class="section-title">02 Equipamento & Avaliação Técnica</div>
            <p><strong>Tipo:</strong> {os_item['tipo_equip']} | <strong>Marca:</strong> {os_item['marca'] or '-'} | <strong>Modelo:</strong> {os_item['equipamento']}</p>
            <p><strong>Nº Série / Patrimônio:</strong> {os_item['ns_patrimonio'] or 'Não informado'}</p>
            <p><strong>Defeito Relatado:</strong> {os_item['defeito'] or '-'}</p>
            <p><strong>Constatação / Diagnóstico:</strong> {os_item['diagnostico'] or 'Em análise'}</p>

            <div class="section-title">03 Peças e Serviços</div>
            <table>
                <thead>
                    <tr><th>Tipo</th><th>Descrição</th><th style="text-align:center;">Qtd</th><th style="text-align:right;">Total (R$)</th></tr>
                </thead>
                <tbody>
                    {itens_linhas_html}
                </tbody>
            </table>
            <p style="text-align: right; font-weight: bold; font-size: 14px; color: #002060; margin-top: 10px;">
                TOTAL GERAL: R$ {(os_item['valor'] or 0.0):.2f}
            </p>
        </div>
    </body>
    </html>
    """

@app.route('/entrada/imprimir/<int:id>')
def imprimir_entrada(id):
    conn = get_db_connection()
    e = conn.execute("SELECT * FROM ordem_entrada WHERE id = ?", (id,)).fetchone()
    conn.close()
    if not e:
        flash("Registro não encontrado.", "danger")
        return redirect(url_for('ordem_entrada'))
    
    data_formatada = datetime.strptime(e['data_entrada'], "%Y-%m-%d").strftime("%d/%m/%Y") if e['data_entrada'] else ""

    def gerar_via_entrada(tipo_via):
        return f"""
        <div class="via-box">
            <div class="row header-print align-items-center">
                <div class="col-8 d-flex align-items-center">
                    <img src="/static/logo.png" alt="Logo" class="logo-img me-2" onerror="this.style.display='none'">
                    <div>
                        <h3 class="mb-1" style="font-weight: 900; color: #002060; font-size: 15px;">CLÍNICA DO HARDWARE</h3>
                        <p class="mb-0 small text-muted" style="font-size: 10px;"><strong>CNPJ:</strong> 70.017.290/0001-61 | <strong>Tel:</strong> (98) 9 8482-9705</p>
                    </div>
                </div>
                <div class="col-4 text-end">
                    <span class="badge bg-secondary mb-1" style="font-size: 10px;">{tipo_via}</span>
                    <h5 class="text-danger mb-0" style="font-weight: bold; font-size: 11px;">COMPROVANTE DE ENTRADA</h5>
                    <h5 class="mb-0" style="color: #002060; font-size: 13px;"><strong>Nº ENT-{e['id']:04d}</strong></h5>
                    <small class="text-muted" style="font-size: 10px;">Data: {data_formatada}</small>
                </div>
            </div>

            <div class="section-title">01 DADOS DO CLIENTE</div>
            <div class="row mb-1">
                <div class="col-8"><p class="mb-1"><strong>Cliente / Razão social:</strong> {e['cliente']}</p></div>
                <div class="col-4"><p class="mb-1"><strong>CPF/CNPJ:</strong> {e['cpf_cnpj'] or 'Não informado'}</p></div>
                <div class="col-12"><p class="mb-0"><strong>Contato / WhatsApp:</strong> {e['contato'] or 'Não informado'}</p></div>
            </div>

            <div class="section-title">02 IDENTIFICAÇÃO DO EQUIPAMENTO</div>
            <div class="row mb-1">
                <div class="col-md-4"><p class="mb-1"><strong>Tipo:</strong> {e['tipo_equip']}</p></div>
                <div class="col-md-4"><p class="mb-1"><strong>Marca:</strong> {e['marca'] or 'Não informada'}</p></div>
                <div class="col-md-4"><p class="mb-1"><strong>Modelo:</strong> {e['equipamento']}</p></div>
                <div class="col-md-6"><p class="mb-1"><strong>Nº de Série / Patrimônio:</strong> {e['ns_patrimonio'] or 'Não informado'}</p></div>
                <div class="col-md-6"><p class="mb-1"><strong>Acessórios entregues:</strong> {e['acessorios'] or 'Nenhum'}</p></div>
                <div class="col-12"><p class="mb-1"><strong>Condição visual:</strong> {e['condicao'] or 'Normal'}</p></div>
            </div>

            <div class="section-title">03 DEFEITO RELATADO</div>
            <div class="row mb-1">
                <div class="col-12">
                    <p class="mb-0 p-1 bg-light border rounded" style="font-size: 11px;"><strong>Defeito relatado:</strong> {e['defeito'] or 'Não especificado'}</p>
                </div>
            </div>

            <div class="footer-terms text-center">
                <p class="mb-0"><strong>Termos:</strong> Orçamento sujeito à análise técnica (Prazo: até 48h). Não nos responsabilizamos por aparelhos deixados por mais de 90 dias.</p>
            </div>

            <div class="row mt-3 text-center">
                <div class="col-6">
                    <div style="border-top: 1px solid #000; width: 85%; margin: auto; padding-top: 2px; font-size: 10px;">Assinatura do Cliente</div>
                </div>
                <div class="col-6">
                    <div style="border-top: 1px solid #000; width: 85%; margin: auto; padding-top: 2px; font-size: 10px;">Clínica do Hardware</div>
                </div>
            </div>
        </div>
        """

    print_template = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Comprovante de Entrada - ENT-{e['id']:04d}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body {{ background: #fff; color: #000; font-family: Arial, sans-serif; padding: 5px; font-size: 11px; }}
            .via-box {{ padding: 10px 15px; background: #fff; height: 48vh; box-sizing: border-box; display: flex; flex-direction: column; justify-content: space-between; }}
            .header-print {{ border-bottom: 2px solid #002060; padding-bottom: 6px; margin-bottom: 6px; }}
            .section-title {{ background-color: #f0f4f8; border-left: 4px solid #002060; padding: 3px 6px; font-weight: bold; font-size: 11px; margin-top: 6px; margin-bottom: 4px; text-transform: uppercase; color: #002060; }}
            .footer-terms {{ font-size: 9px; color: #555; background: #f9f9f9; padding: 4px; border: 1px solid #ddd; border-radius: 3px; margin-top: 6px; }}
            .logo-img {{ max-height: 40px; max-width: 140px; object-fit: contain; }}
            .linha-recorte {{ border-top: 2px dashed #666; margin: 5px 0; position: relative; text-align: center; }}
            .linha-recorte span {{ background: #fff; padding: 0 10px; font-size: 10px; color: #666; position: relative; top: -9px; font-weight: bold; text-transform: uppercase; }}
            @media print {{
                .no-print {{ display: none !important; }}
                body {{ padding: 0; margin: 0; }}
                @page {{ size: A4; margin: 5mm; }}
            }}
        </style>
    </head>
    <body onload="window.print()">
        {gerar_via_entrada("1ª VIA - CLIENTE")}
        <div class="linha-recorte"><span>✂️ DESTACAR / RECORTAR AQUI ✂️</span></div>
        {gerar_via_entrada("2ª VIA - EMPRESA")}

        <div class="text-center mt-2 no-print">
            <button onclick="window.print()" class="btn btn-primary btn-sm"><i class="fas fa-print"></i> Imprimir / Salvar PDF</button>
            <a href="/entrada" class="btn btn-secondary btn-sm">Voltar</a>
        </div>
    </body>
    </html>
    """
    return print_template

@app.route('/entrada/imprimir_via_unica/<int:id>')
def imprimir_entrada_via_unica(id):
    conn = get_db_connection()
    e = conn.execute("SELECT * FROM ordem_entrada WHERE id = ?", (id,)).fetchone()
    conn.close()
    if not e:
        flash("Registro não encontrado.", "danger")
        return redirect(url_for('ordem_entrada'))
    
    data_formatada = datetime.strptime(e['data_entrada'], "%Y-%m-%d").strftime("%d/%m/%Y") if e['data_entrada'] else ""

    print_template = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Comprovante de Entrada (Via Única) - ENT-{e['id']:04d}</title>
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
                    <h5 class="text-danger mb-0" style="font-weight: bold; font-size: 13px;">COMPROVANTE DE ENTRADA</h5>
                    <h5 class="mb-0" style="color: #002060; font-size: 15px;"><strong>Nº ENT-{e['id']:04d}</strong></h5>
                    <small class="text-muted" style="font-size: 11px;">Data: {data_formatada}</small>
                </div>
            </div>

            <div class="section-title">01 DADOS DO CLIENTE</div>
            <div class="row mb-2">
                <div class="col-8"><p class="mb-1"><strong>Cliente / Razão social:</strong> {e['cliente']}</p></div>
                <div class="col-4"><p class="mb-1"><strong>CPF/CNPJ:</strong> {e['cpf_cnpj'] or 'Não informado'}</p></div>
                <div class="col-12"><p class="mb-0"><strong>Contato / WhatsApp:</strong> {e['contato'] or 'Não informado'}</p></div>
            </div>

            <div class="section-title">02 IDENTIFICAÇÃO DO EQUIPAMENTO</div>
            <div class="row mb-2">
                <div class="col-md-4"><p class="mb-1"><strong>Tipo:</strong> {e['tipo_equip']}</p></div>
                <div class="col-md-4"><p class="mb-1"><strong>Marca:</strong> {e['marca'] or 'Não informada'}</p></div>
                <div class="col-md-4"><p class="mb-1"><strong>Modelo:</strong> {e['equipamento']}</p></div>
                <div class="col-md-6"><p class="mb-1"><strong>Nº de Série / Patrimônio:</strong> {e['ns_patrimonio'] or 'Não informado'}</p></div>
                <div class="col-md-6"><p class="mb-1"><strong>Acessórios entregues:</strong> {e['acessorios'] or 'Nenhum'}</p></div>
                <div class="col-12"><p class="mb-1"><strong>Condição visual:</strong> {e['condicao'] or 'Normal'}</p></div>
            </div>

            <div class="section-title">03 DEFEITO RELATADO</div>
            <div class="row mb-2">
                <div class="col-12">
                    <p class="mb-0 p-2 bg-light border rounded" style="font-size: 12px;"><strong>Defeito relatado:</strong> {e['defeito'] or 'Não especificado'}</p>
                </div>
            </div>

            <div class="footer-terms text-center">
                <p class="mb-0"><strong>Termos:</strong> Orçamento sujeito à análise técnica (Prazo: até 48h). Não nos responsabilizamos por aparelhos deixados por mais de 90 dias.</p>
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
            <a href="/entrada" class="btn btn-secondary btn-sm">Voltar</a>
        </div>
    </body>
    </html>
    """
    return print_template

@app.route('/entrada/enviar_email/<int:id>')
def enviar_email_entrada(id):
    conn = get_db_connection()
    e = conn.execute("SELECT * FROM ordem_entrada WHERE id = ?", (id,)).fetchone()
    conn.close()
    if not e or not e['email']:
        flash("E-mail do cliente não cadastrado para este registro.", "danger")
        return redirect(url_for('ordem_entrada'))
    
    data_formatada = datetime.strptime(e['data_entrada'], "%Y-%m-%d").strftime("%d/%m/%Y") if e['data_entrada'] else datetime.now().strftime("%d/%m/%Y")
    
    assunto = f"Envio de Ordem de Entrada Nº {e['id']:04d} - {e['equipamento']} | {e['cliente']}"
    corpo_html = f"""
    <div style="font-family: Arial, sans-serif; color: #333; padding: 25px; border: 1px solid #002060; border-radius: 8px; max-width: 600px; margin: auto; background-color: #ffffff;">
        <h2 style="color: #002060; border-bottom: 2px solid #002060; padding-bottom: 10px; margin-top: 0;">CLÍNICA DO HARDWARE</h2>
        <p>Prezado(a) <strong>{e['cliente']}</strong>,</p>
        <p>Espero que se encontre bem.</p>
        <p>Segue em anexo a <strong>Ordem de Entrada Nº {e['id']:04d}</strong> referente ao equipamento <strong>{e['tipo_equip']} {e['marca'] or ''} {e['equipamento']}</strong> (Patrimônio/Série: <strong>{e['ns_patrimonio'] or 'Não informado'}</strong>), deixado nas nossas instalações no dia <strong>{data_formatada}</strong>.</p>
        
        <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #002060; margin: 15px 0; border-radius: 4px;">
            <p style="margin: 0 0 8px 0;"><strong>Resumo da Entrada:</strong></p>
            <ul style="margin: 0; padding-left: 20px;">
                <li><strong>Status:</strong> Em análise na recepção</li>
                <li><strong>Defeito Relatado:</strong> {e['defeito'] or 'Não especificado'}</li>
                <li><strong>Acessórios Deixados:</strong> {e['acessorios'] or 'Nenhum'}</li>
            </ul>
        </div>
        
        <p>Ficamos a aguardar a conclusão da avaliação técnica para enviar o orçamento detalhado.</p>
        <p>Caso tenha alguma dúvida ou necessite de esclarecimentos adicionais, estamos à inteira disposição.</p>
        <br>
        <p style="margin-bottom: 0;">Com os melhores cumprimentos,</p>
        <p style="font-weight: bold; color: #002060; margin-top: 4px;">Clínica do Hardware</p>
        <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
        <p style="font-size: 12px; color: #666; text-align: center; margin: 0;">Tel: (98) 9 8482-9705 | São Luís - MA</p>
    </div>
    """
    
    # Gera o PDF em memória para anexo
    html_pdf = gerar_html_comprovante_entrada(e)
    pdf_bytes = None
    try:
        import pdfkit
        pdf_bytes = pdfkit.from_string(html_pdf, False)
    except Exception:
        pdf_bytes = html_pdf.encode('utf-8')  # Fallback caso pdfkit não esteja instalado

    nome_pdf = f"Ordem_Entrada_{e['id']:04d}.pdf"
    sucesso, mensagem = enviar_email_com_anexo_smtp(e['email'], assunto, corpo_html, pdf_bytes, nome_pdf)
    
    if sucesso:
        flash("E-mail com Ordem de Entrada em PDF enviado com sucesso pelo Gmail!", "success")
    else:
        flash(f"Erro ao enviar e-mail: {mensagem}", "danger")
        
    return redirect(url_for('ordem_entrada'))

@app.route('/entrada/excluir/<int:id>')
def excluir_entrada(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM ordem_entrada WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Registro de entrada excluído com sucesso!", "success")
    return redirect(url_for('ordem_entrada'))

@app.route('/os/nova_de_entrada/<int:id>', methods=['GET', 'POST'])
def nova_os_de_entrada(id):
    conn = get_db_connection()
    entrada = conn.execute("SELECT * FROM ordem_entrada WHERE id = ?", (id,)).fetchone()
    
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

        cursor = conn.cursor()
        cursor.execute("""INSERT INTO ordens_servico 
                          (cliente, cpf_cnpj, contato, email_end, tipo_equip, marca, equipamento, ns_patrimonio, 
                           acessorios, condicao, status, defeito, diagnostico, servico, servicos_json, peca_utilizada, pecas_json, valor_pecas, valor_servico, valor, data_abertura) 
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       (cliente, cpf_cnpj, contato, email_end, tipo_equip, marca, equipamento, ns_patrimonio,
                        acessorios, condicao, status, defeito, diagnostico, servico_str, servicos_json, peca_utilizada_str, pecas_json, valor_pecas, valor_servico, valor_total, data_hoje))
        os_id = cursor.lastrowid

        cursor.execute("INSERT INTO boletos (cliente, numero_documento, valor, data_vencimento, status) VALUES (?, ?, ?, ?, ?)",
                       (cliente, f"OS-{os_id:04d}", valor_total, data_hoje, "Gerado (Aguardando Pagamento)"))
        
        conn.execute("DELETE FROM ordem_entrada WHERE id = ?", (id,))
        conn.commit()
        conn.close()
        flash("Ordem de Serviço gerada a partir da Entrada com sucesso!", "success")
        return redirect(url_for('index'))

    lista_servicos = conn.execute("SELECT * FROM servicos_cadastrados ORDER BY nome_servico ASC").fetchall()
    lista_pecas = conn.execute("SELECT * FROM pecas_estoque ORDER BY nome_peca ASC").fetchall()
    conn.close()

    servicos_dict_list = [{"nome_servico": s["nome_servico"], "valor_padrao": s["valor_padrao"]} for s in lista_servicos]
    pecas_dict_list = [{"nome_peca": p["nome_peca"], "quantidade": p["quantidade"], "valor_venda": p["valor_venda"]} for p in lista_pecas]
    
    html_page = BASE_TEMPLATE.replace("{% block content %}{% endblock %}", f"""
    <div class="header-custom">
        <h2><i class="fas fa-file-invoice-dollar"></i> Gerar Orçamento / O.S. (Via Check-in ENT-{id:04d})</h2>
    </div>
    <div class="card p-4">
        <form method="POST">
            <input type="hidden" id="servicos_json_input" name="servicos_json">
            <input type="hidden" id="pecas_json_input" name="pecas_json">
            <div class="row g-3">
                <div class="col-md-6">
                    <label class="form-label">Cliente / Razão Social:</label>
                    <input type="text" class="form-control" id="cliente_field" name="cliente" value="{entrada['cliente'] or ''}" required>
                </div>
                <div class="col-md-6">
                    <label class="form-label">CPF / CNPJ:</label>
                    <input type="text" class="form-control" id="cpf_cnpj_field" name="cpf_cnpj" value="{entrada['cpf_cnpj'] or ''}" onblur="consultarCnpjCompleto('cpf_cnpj_field', 'cliente_field', 'contato_field', 'email_field')">
                </div>
                <div class="col-md-6">
                    <label class="form-label">Contato (WhatsApp):</label>
                    <input type="text" class="form-control" id="contato_field" name="contato" value="{entrada['contato'] or ''}">
                </div>
                <div class="col-md-6">
                    <label class="form-label">E-mail do Cliente:</label>
                    <input type="email" class="form-control" id="email_field" name="email_end" value="{entrada['email'] or ''}">
                </div>
                <div class="col-md-4">
                    <label class="form-label">Tipo de Equipamento:</label>
                    <input type="text" class="form-control" name="tipo_equip" value="{entrada['tipo_equip'] or ''}">
                </div>
                <div class="col-md-4">
                    <label class="form-label">Marca:</label>
                    <input type="text" class="form-control" name="marca" value="{entrada['marca'] or ''}">
                </div>
                <div class="col-md-4">
                    <label class="form-label">Modelo:</label>
                    <input type="text" class="form-control" name="equipamento" value="{entrada['equipamento'] or ''}" required>
                </div>
                <div class="col-md-6">
                    <label class="form-label">Nº de Série / Patrimônio:</label>
                    <input type="text" class="form-control" name="ns_patrimonio" value="{entrada['ns_patrimonio'] or ''}">
                </div>
                <div class="col-md-6">
                    <label class="form-label">Acessórios:</label>
                    <input type="text" class="form-control" name="acessorios" value="{entrada['acessorios'] or ''}">
                </div>
                <div class="col-md-12">
                    <label class="form-label">Condição Visual:</label>
                    <input type="text" class="form-control" name="condicao" value="{entrada['condicao'] or ''}">
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
                    <textarea class="form-control" name="defeito" rows="2">{entrada['defeito'] or ''}</textarea>
                </div>
                <div class="col-md-12">
                    <label class="form-label">Diagnóstico Técnico / Constatação:</label>
                    <textarea class="form-control" name="diagnostico" rows="2"></textarea>
                </div>

                <!-- SERVIÇOS DINÂMICOS -->
                <div class="col-md-12 p-3 bg-light border rounded">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <label class="form-label fw-bold mb-0 text-primary"><i class="fas fa-tools"></i> Serviços a Executar (Múltiplos Serviços & Quantidade):</label>
                        <button type="button" class="btn btn-sm btn-primary" onclick="adicionarLinhaServico()"><i class="fas fa-plus"></i> Adicionar Serviço</button>
                    </div>
                    <div id="container-servicos"></div>
                </div>

                <!-- PEÇAS DINÂMICAS -->
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
                <button type="submit" class="btn btn-success"><i class="fas fa-save"></i> Criar O.S. Definitiva & Gerar Boleto</button>
                <a href="/entrada" class="btn btn-secondary">Voltar</a>
            </div>
        </form>
    </div>
    <script>
        inicializarServicosDisponiveis({json.dumps(servicos_dict_list)});
        inicializarPecasDisponiveis({json.dumps(pecas_dict_list)});
        adicionarLinhaServico();
    </script>
    """)
    return render_template_string(html_page, active_tab='entrada')

@app.route('/')
def index():
    conn = get_db_connection()
    raw_os_list = conn.execute("SELECT * FROM ordens_servico ORDER BY id DESC").fetchall()
    conn.close()
    
    os_list = []
    for row in raw_os_list:
        item = dict(row)
        item['os_formatada'] = f"OS-{item['id']:04d}"
        os_list.append(item)

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
                    {''.join([f"<tr><td><strong>" + r['os_formatada'] + f"</strong></td><td>" + str(r['cliente']) + f"</td><td>" + str(r['equipamento']) + f"</td><td>R$ " + f"{r['valor']:.2f}" + f"</td><td><select class='form-select form-select-sm fw-bold ' style='width: 175px;' onchange='alterarStatusRapido(" + str(r['id']) + f", this.value)'><option value='Aguardando Aprovação' " + ('selected' if r['status'] == 'Aguardando Aprovação' else '') + f">Aguardando Aprovação</option><option value='Em Execução' " + ('selected' if r['status'] == 'Em Execução' else '') + f">Em Execução</option><option value='Executado' " + ('selected' if r['status'] == 'Executado' else '') + f">Executado</option></select></td><td>" + str(r['data_abertura']) + f"</td><td>" +
                    f"<div class='btn-group btn-group-sm mb-1'>" +
                    f"<a href='/os/imprimir/" + str(r['id']) + f"' class='btn btn-primary' target='_blank' title='2 Vias (Imprimir/PDF)'><i class='fas fa-print'></i> 2 Vias</a>" +
                    f"<a href='/os/imprimir_via_unica/" + str(r['id']) + f"' class='btn btn-outline-primary' target='_blank' title='Via Única Cliente' style='background:#e7f1ff;'><i class='fas fa-file-alt'></i> Via Única</a>" +
                    f"</div>" +
                    f"<div class='btn-group btn-group-sm'>" +
                    f"<a href='/os/enviar_email/" + str(r['id']) + f"' class='btn btn-warning' title='Enviar por E-mail (Gmail)'><i class='fas fa-envelope'></i></a>" +
                    f"<a href='https://api.whatsapp.com/send?phone=55" + ''.join(filter(str.isdigit, str(r['contato'] or ''))) + f"&text=" + urllib.parse.quote(f"Olá *{r['cliente']}*, sua O.S. *OS-{r['id']:04d}* referente ao equipamento *{r['tipo_equip']} {r['marca'] or ''} {r['equipamento']}* encontra-se com status: *{r['status']}*. Valor total: R$ {r['valor']:.2f}. Agradecemos a preferência!") + f"' target='_blank' class='btn btn-success' title='Enviar no WhatsApp'><i class='fab fa-whatsapp'></i></a>" +
                    f"<a href='/os/editar/" + str(r['id']) + f"' class='btn btn-secondary' title='Editar'><i class='fas fa-edit'></i></a>" +
                    f"<a href='/os/excluir/" + str(r['id']) + f"' class='btn btn-danger' onclick=\"return confirm('Deseja excluir esta O.S.?')\" title='Excluir'><i class='fas fa-trash'></i></a>" +
                    f"</div>" +
                    f"</td></tr>" for r in os_list]) if os_list else "<tr><td colspan='7' class='text-center text-muted'>Nenhuma Ordem de Serviço cadastrada.</td></tr>"}
                </tbody>
            </table>
        </div>
    </div>
    """)
    return render_template_string(html_page, active_tab='os', os_list=os_list)

@app.route('/os/imprimir/<int:id>')
def imprimir_os(id):
    conn = get_db_connection()
    os_item = conn.execute("SELECT * FROM ordens_servico WHERE id = ?", (id,)).fetchone()
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
    os_item = conn.execute("SELECT * FROM ordens_servico WHERE id = ?", (id,)).fetchone()
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
    os_item = conn.execute("SELECT * FROM ordens_servico WHERE id = ?", (id,)).fetchone()
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
    
    # Gera o PDF em memória para anexo
    html_pdf = gerar_html_os(os_item)
    pdf_bytes = None
    try:
        import pdfkit
        pdf_bytes = pdfkit.from_string(html_pdf, False)
    except Exception:
        pdf_bytes = html_pdf.encode('utf-8')  # Fallback caso pdfkit não esteja instalado

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
        conn.execute("UPDATE ordens_servico SET status = ? WHERE id = ?", (novo_status, id))
        conn.commit()
        conn.close()
        return jsonify({'sucesso': True})
    return jsonify({'sucesso': False}), 400

@app.route('/os/nova', methods=['GET', 'POST'])
def nova_os():
    conn = get_db_connection()
    
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

        cursor = conn.cursor()
        cursor.execute("""INSERT INTO ordens_servico 
                          (cliente, cpf_cnpj, contato, email_end, tipo_equip, marca, equipamento, ns_patrimonio, 
                           acessorios, condicao, status, defeito, diagnostico, servico, servicos_json, peca_utilizada, pecas_json, valor_pecas, valor_servico, valor, data_abertura) 
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       (cliente, cpf_cnpj, contato, email_end, tipo_equip, marca, equipamento, ns_patrimonio,
                        acessorios, condicao, status, defeito, diagnostico, servico_str, servicos_json, peca_utilizada_str, pecas_json, valor_pecas, valor_servico, valor_total, data_hoje))
        os_id = cursor.lastrowid

        cursor.execute("INSERT INTO boletos (cliente, numero_documento, valor, data_vencimento, status) VALUES (?, ?, ?, ?, ?)",
                       (cliente, f"OS-{os_id:04d}", valor_total, data_hoje, "Gerado (Aguardando Pagamento)"))
        conn.commit()
        conn.close()
        flash("Ordem de Serviço salva e Boleto gerado com sucesso!", "success")
        return redirect(url_for('index'))

    entradas_pendentes = conn.execute("SELECT * FROM ordem_entrada ORDER BY id DESC").fetchall()
    lista_servicos = conn.execute("SELECT * FROM servicos_cadastrados ORDER BY nome_servico ASC").fetchall()
    lista_pecas = conn.execute("SELECT * FROM pecas_estoque ORDER BY nome_peca ASC").fetchall()
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

                <!-- SERVIÇOS DINÂMICOS -->
                <div class="col-md-12 p-3 bg-light border rounded">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <label class="form-label fw-bold mb-0 text-primary"><i class="fas fa-tools"></i> Serviços a Executar (Múltiplos Serviços & Quantidade):</label>
                        <button type="button" class="btn btn-sm btn-primary" onclick="adicionarLinhaServico()"><i class="fas fa-plus"></i> Adicionar Serviço</button>
                    </div>
                    <div id="container-servicos"></div>
                </div>

                <!-- PEÇAS DINÂMICAS -->
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
    os_item = conn.execute("SELECT * FROM ordens_servico WHERE id = ?", (id,)).fetchone()
    
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

        conn.execute("""UPDATE ordens_servico SET 
                        cliente = ?, cpf_cnpj = ?, contato = ?, email_end = ?, 
                        tipo_equip = ?, marca = ?, equipamento = ?, ns_patrimonio = ?, 
                        acessorios = ?, condicao = ?, status = ?, 
                        defeito = ?, diagnostico = ?, servico = ?, servicos_json = ?, peca_utilizada = ?, pecas_json = ?,
                        valor_pecas = ?, valor_servico = ?, valor = ? WHERE id = ?""",
                     (cliente, cpf_cnpj, contato, email_end, tipo_equip, marca, equipamento, ns_patrimonio,
                      acessorios, condicao, status, defeito, diagnostico, servico_str, servicos_json, peca_utilizada_str, pecas_json,
                      valor_pecas, valor_servico, valor_total, id))
        conn.execute("UPDATE boletos SET cliente = ?, valor = ? WHERE numero_documento = ?",
                     (cliente, valor_total, f"OS-{id:04d}"))
        conn.commit()
        conn.close()
        flash("Ordem de Serviço atualizada com sucesso!", "success")
        return redirect(url_for('index'))

    lista_servicos = conn.execute("SELECT * FROM servicos_cadastrados ORDER BY nome_servico ASC").fetchall()
    lista_pecas = conn.execute("SELECT * FROM pecas_estoque ORDER BY nome_peca ASC").fetchall()
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

                <!-- SERVIÇOS DINÂMICOS -->
                <div class="col-md-12 p-3 bg-light border rounded">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <label class="form-label fw-bold mb-0 text-primary"><i class="fas fa-tools"></i> Serviços a Executar (Múltiplos Serviços & Quantidade):</label>
                        <button type="button" class="btn btn-sm btn-primary" onclick="adicionarLinhaServico()"><i class="fas fa-plus"></i> Adicionar Serviço</button>
                    </div>
                    <div id="container-servicos"></div>
                </div>

                <!-- PEÇAS DINÂMICAS -->
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
    conn.execute("DELETE FROM boletos WHERE numero_documento = ?", (f"OS-{id:04d}",))
    conn.execute("DELETE FROM ordens_servico WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Ordem de Serviço excluída com sucesso!", "success")
    return redirect(url_for('index'))

@app.route('/clientes', methods=['GET', 'POST'])
def clientes():
    conn = get_db_connection()
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

        conn.execute("""INSERT INTO clientes (nome, cpf_cnpj, contato, email, cep, rua, numero, bairro, complemento, cidade_uf) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (nome, cpf_cnpj, contato, email, cep, rua, numero, bairro, complemento, cidade_uf))
        conn.commit()
        conn.close()
        flash("Cliente cadastrado com sucesso!", "success")
        return redirect(url_for('clientes'))
    
    lista = conn.execute("SELECT * FROM clientes ORDER BY id DESC").fetchall()
    conn.close()
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
                    {''.join([f"<tr><td>" + str(c['id']) + f"</td><td>" + str(c['nome']) + f"</td><td>" + str(c['cpf_cnpj'] or '') + f"</td><td>" + str(c['contato'] or '') + f"</td><td>" + str(c['cidade_uf'] or '') + f"</td><td><a href='/clientes/editar/" + str(c['id']) + f"' class='btn btn-sm btn-warning'><i class='fas fa-edit'></i></a> <a href='/clientes/excluir/" + str(c['id']) + f"' class='btn btn-sm btn-danger' onclick=\"return confirm('Deseja excluir este cliente?')\"><i class='fas fa-trash'></i></a></td></tr>" for c in lista]) if lista else "<tr><td colspan='6' class='text-center text-muted'>Nenhum cliente cadastrado.</td></tr>"}
                </tbody>
            </table>
        </div>
    </div>
    """)
    return render_template_string(html_page, active_tab='clientes', lista=lista)

@app.route('/clientes/editar/<int:id>', methods=['GET', 'POST'])
def editar_cliente(id):
    conn = get_db_connection()
    c = conn.execute("SELECT * FROM clientes WHERE id = ?", (id,)).fetchone()
    
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

        conn.execute("""UPDATE clientes SET nome = ?, cpf_cnpj = ?, contato = ?, email = ?, 
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
    conn.execute("DELETE FROM clientes WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Cliente excluído com sucesso!", "success")
    return redirect(url_for('clientes'))

@app.route('/servicos', methods=['GET', 'POST'])
def servicos():
    conn = get_db_connection()
    if request.method == 'POST':
        nome = request.form['nome_servico']
        desc = request.form['descricao']
        valor = float(request.form['valor_padrao'] or 0)
        conn.execute("INSERT INTO servicos_cadastrados (nome_servico, descricao, valor_padrao) VALUES (?, ?, ?)", (nome, desc, valor))
        conn.commit()
        conn.close()
        flash("Serviço cadastrado com sucesso!", "success")
        return redirect(url_for('servicos'))
    lista = conn.execute("SELECT * FROM servicos_cadastrados").fetchall()
    conn.close()
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
                    {''.join([f"<tr><td>" + str(s['id']) + f"</td><td>" + str(s['nome_servico']) + f"</td><td>" + str(s['descricao'] or '') + f"</td><td>R$ " + f"{s['valor_padrao']:.2f}" + f"</td><td><a href='/servicos/editar/" + str(s['id']) + f"' class='btn btn-sm btn-warning' title='Editar'><i class='fas fa-edit'></i></a> <a href='/servicos/excluir/" + str(s['id']) + f"' class='btn btn-sm btn-danger' onclick=\"return confirm('Deseja excluir este serviço?')\" title='Excluir'><i class='fas fa-trash'></i></a></td></tr>" for s in lista]) if lista else "<tr><td colspan='5' class='text-center text-muted'>Nenhum serviço cadastrado.</td></tr>"}
                </tbody>
            </table>
        </div>
    </div>
    """)
    return render_template_string(html_page, active_tab='servicos', lista=lista)

@app.route('/servicos/editar/<int:id>', methods=['GET', 'POST'])
def editar_servico(id):
    conn = get_db_connection()
    s = conn.execute("SELECT * FROM servicos_cadastrados WHERE id = ?", (id,)).fetchone()
    
    if request.method == 'POST':
        nome = request.form['nome_servico']
        desc = request.form['descricao']
        valor = float(request.form['valor_padrao'] or 0)
        conn.execute("UPDATE servicos_cadastrados SET nome_servico = ?, descricao = ?, valor_padrao = ? WHERE id = ?",
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
    conn.execute("DELETE FROM servicos_cadastrados WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Serviço excluído com sucesso!", "success")
    return redirect(url_for('servicos'))

@app.route('/pecas', methods=['GET', 'POST'])
def pecas():
    conn = get_db_connection()
    if request.method == 'POST':
        nome = request.form['nome_peca']
        codigo = request.form['codigo']
        qtd = int(request.form['quantidade'] or 1)
        custo = float(request.form['valor_custo'] or 0)
        venda = float(request.form['valor_venda'] or 0)
        conn.execute("INSERT INTO pecas_estoque (nome_peca, codigo, quantidade, valor_custo, valor_venda) VALUES (?, ?, ?, ?, ?)",
                     (nome, codigo, qtd, custo, venda))
        conn.commit()
        conn.close()
        flash("Peça cadastrada no estoque!", "success")
        return redirect(url_for('pecas'))
    lista = conn.execute("SELECT * FROM pecas_estoque").fetchall()
    conn.close()
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
                    {''.join([f"<tr><td>" + str(p['id']) + f"</td><td>" + str(p['nome_peca']) + f"</td><td>" + str(p['codigo'] or '') + f"</td><td>" + str(p['quantidade']) + f"</td><td>R$ " + f"{p['valor_custo']:.2f}" + f"</td><td>R$ " + f"{p['valor_venda']:.2f}" + f"</td><td><a href='/pecas/editar/" + str(p['id']) + f"' class='btn btn-sm btn-warning' title='Editar'><i class='fas fa-edit'></i></a> <a href='/pecas/excluir/" + str(p['id']) + f"' class='btn btn-sm btn-danger' onclick=\"return confirm('Deseja excluir esta peça?')\" title='Excluir'><i class='fas fa-trash'></i></a></td></tr>" for p in lista]) if lista else "<tr><td colspan='7' class='text-center text-muted'>Nenhuma peça no estoque.</td></tr>"}
                </tbody>
            </table>
        </div>
    </div>
    """)
    return render_template_string(html_page, active_tab='pecas', lista=lista)

@app.route('/pecas/editar/<int:id>', methods=['GET', 'POST'])
def editar_peca(id):
    conn = get_db_connection()
    p = conn.execute("SELECT * FROM pecas_estoque WHERE id = ?", (id,)).fetchone()
    
    if request.method == 'POST':
        nome = request.form['nome_peca']
        codigo = request.form['codigo']
        qtd = int(request.form['quantidade'] or 1)
        custo = float(request.form['valor_custo'] or 0)
        venda = float(request.form['valor_venda'] or 0)
        conn.execute("UPDATE pecas_estoque SET nome_peca = ?, codigo = ?, quantidade = ?, valor_custo = ?, valor_venda = ? WHERE id = ?",
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
    conn.execute("DELETE FROM pecas_estoque WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Peça excluída com sucesso!", "success")
    return redirect(url_for('pecas'))

@app.route('/boletos', methods=['GET', 'POST'])
def boletos():
    conn = get_db_connection()
    if request.method == 'POST':
        cliente = request.form['cliente']
        doc = request.form['numero_documento']
        valor = float(request.form['valor'] or 0)
        venc = request.form['data_vencimento']
        conn.execute("INSERT INTO boletos (cliente, numero_documento, valor, data_vencimento, status) VALUES (?, ?, ?, ?, 'Gerado (Aguardando Pagamento)')",
                     (cliente, doc, valor, venc))
        conn.commit()
        conn.close()
        flash("Boleto gerado com sucesso!", "success")
        return redirect(url_for('boletos'))
    lista = conn.execute("SELECT * FROM boletos").fetchall()
    conn.close()
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
                    {''.join([f"<tr><td>" + str(b['id']) + f"</td><td>" + str(b['cliente']) + f"</td><td>" + str(b['numero_documento']) + f"</td><td>R$ " + f"{b['valor']:.2f}" + f"</td><td>" + str(b['data_vencimento']) + f"</td><td><span class='badge bg-" + ('success' if b['status'] == 'Pago' else 'warning') + f"'>" + str(b['status']) + f"</span></td><td>" + (f"<a href='/boletos/pagar/" + str(b['id']) + f"' class='btn btn-sm btn-success me-1' title='Marcar como Pago'><i class='fas fa-check'></i></a>" if b['status'] != 'Pago' else '') + f"<a href='/boletos/editar/" + str(b['id']) + f"' class='btn btn-sm btn-warning me-1' title='Editar'><i class='fas fa-edit'></i></a> <a href='/boletos/excluir/" + str(b['id']) + f"' class='btn btn-sm btn-danger' onclick=\"return confirm('Deseja excluir este boleto?')\" title='Excluir'><i class='fas fa-trash'></i></a></td></tr>" for b in lista]) if lista else "<tr><td colspan='7' class='text-center text-muted'>Nenhum boleto cadastrado.</td></tr>"}
                </tbody>
            </table>
        </div>
    </div>
    """)
    return render_template_string(html_page, active_tab='boletos', lista=lista)

@app.route('/boletos/editar/<int:id>', methods=['GET', 'POST'])
def editar_boleto(id):
    conn = get_db_connection()
    b = conn.execute("SELECT * FROM boletos WHERE id = ?", (id,)).fetchone()
    
    if request.method == 'POST':
        cliente = request.form['cliente']
        doc = request.form['numero_documento']
        valor = float(request.form['valor'] or 0)
        venc = request.form['data_vencimento']
        status = request.form['status']
        conn.execute("UPDATE boletos SET cliente = ?, numero_documento = ?, valor = ?, data_vencimento = ?, status = ? WHERE id = ?",
                     (cliente, doc, valor, venc, status, id))
        conn.commit()
        conn.close()
        flash("Boleto atualizado com sucesso!", "success")
        return redirect(url_for('boletos'))

    conn.close()
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
                    <option value="Gerado (Aguardando Pagamento)" {'selected' if b['status'] == 'Gerado (Aguardando Pagamento)' else ''}>Gerado (Aguardando Pagamento)</option>
                    <option value="Pago" {'selected' if b['status'] == 'Pago' else ''}>Pago</option>
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
    conn.execute("UPDATE boletos SET status = 'Pago', data_pagamento = ? WHERE id = ?", (hoje, id))
    conn.commit()
    conn.close()
    flash("Boleto marcado como PAGO!", "success")
    return redirect(url_for('boletos'))

@app.route('/boletos/excluir/<int:id>')
def excluir_boleto(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM boletos WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Boleto excluído com sucesso!", "success")
    return redirect(url_for('boletos'))

@app.route('/nfs', methods=['GET', 'POST'])
def nfs():
    conn = get_db_connection()
    if request.method == 'POST':
        num = request.form['numero_nf']
        cliente = request.form['cliente']
        valor = float(request.form['valor'] or 0)
        conn.execute("INSERT INTO notas_fiscais (numero_nf, cliente, valor, data_emissao, status) VALUES (?, ?, ?, ?, 'Emitida')",
                     (num, cliente, valor, datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
        conn.close()
        flash("Nota Fiscal registrada!", "success")
        return redirect(url_for('nfs'))
    lista = conn.execute("SELECT * FROM notas_fiscais").fetchall()
    conn.close()
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
                    {''.join([f"<tr><td>" + str(n['id']) + f"</td><td>" + str(n['numero_nf']) + f"</td><td>" + str(n['cliente']) + f"</td><td>R$ " + f"{n['valor']:.2f}" + f"</td><td>" + str(n['data_emissao']) + f"</td><td><span class='badge bg-success'>" + str(n['status']) + f"</span></td><td><a href='/nfs/editar/" + str(n['id']) + f"' class='btn btn-sm btn-warning me-1' title='Editar'><i class='fas fa-edit'></i></a> <a href='/nfs/excluir/" + str(n['id']) + f"' class='btn btn-sm btn-danger' onclick=\"return confirm('Deseja excluir esta Nota Fiscal?')\" title='Excluir'><i class='fas fa-trash'></i></a></td></tr>" for n in lista]) if lista else "<tr><td colspan='7' class='text-center text-muted'>Nenhuma Nota Fiscal emitida.</td></tr>"}
                </tbody>
            </table>
        </div>
    </div>
    """)
    return render_template_string(html_page, active_tab='nfs', lista=lista)

@app.route('/nfs/editar/<int:id>', methods=['GET', 'POST'])
def editar_nf(id):
    conn = get_db_connection()
    n = conn.execute("SELECT * FROM notas_fiscais WHERE id = ?", (id,)).fetchone()
    
    if request.method == 'POST':
        num = request.form['numero_nf']
        cliente = request.form['cliente']
        valor = float(request.form['valor'] or 0)
        status = request.form['status']
        conn.execute("UPDATE notas_fiscais SET numero_nf = ?, cliente = ?, valor = ?, status = ? WHERE id = ?",
                     (num, cliente, valor, status, id))
        conn.commit()
        conn.close()
        flash("Nota Fiscal atualizada com sucesso!", "success")
        return redirect(url_for('nfs'))

    conn.close()
    html_page = BASE_TEMPLATE.replace("{% block content %}{% endblock %}", f"""
    <div class="header-custom"><h2><i class="fas fa-edit"></i> Editar Nota Fiscal (ID: {n['id']})</h2></div>
    <div class="card p-4">
        <form method="POST" class="row g-3">
            <div class="col-md-6"><label class="form-label">Nº Nota Fiscal:</label><input type="text" class="form-control" name="numero_nf" value="{n['numero_nf'] or ''}" required></div>
            <div class="col-md-6"><label class="form-label">Cliente / Razão Social:</label><input type="text" class="form-control" name="cliente" value="{n['cliente'] or ''}" required></div>
            <div class="col-md-6"><label class="form-label">Valor (R$):</label><input type="number" step="0.01" class="form-control" name="valor" value="{n['valor'] or 0.00}" required></div>
            <div class="col-md-6"><label class="form-label">Status:</label>
                <select class="form-select" name="status">
                    <option value="Emitida" {'selected' if n['status'] == 'Emitida' else ''}>Emitida</option>
                    <option value="Cancelada" {'selected' if n['status'] == 'Cancelada' else ''}>Cancelada</option>
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
    conn.execute("DELETE FROM notas_fiscais WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Nota Fiscal excluída com sucesso!", "success")
    return redirect(url_for('nfs'))

@app.route('/despesas', methods=['GET', 'POST'])
def despesas():
    conn = get_db_connection()
    if request.method == 'POST':
        desc = request.form['descricao']
        cat = request.form['categoria']
        valor = float(request.form['valor'] or 0)
        conn.execute("INSERT INTO despesas (descricao, categoria, valor, data_despesa) VALUES (?, ?, ?, ?)",
                     (desc, cat, valor, datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
        conn.close()
        flash("Despesa registrada com sucesso!", "success")
        return redirect(url_for('despesas'))
    lista = conn.execute("SELECT * FROM despesas ORDER BY data_despesa DESC").fetchall()
    conn.close()
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
                    {''.join([f"<tr><td>" + str(d['id']) + f"</td><td>" + str(d['descricao']) + f"</td><td>" + str(d['categoria']) + f"</td><td class='text-danger'>R$ " + f"{d['valor']:.2f}" + f"</td><td>" + str(d['data_despesa']) + f"</td><td><a href='/despesas/editar/" + str(d['id']) + f"' class='btn btn-sm btn-warning me-1' title='Editar'><i class='fas fa-edit'></i></a> <a href='/despesas/excluir/" + str(d['id']) + f"' class='btn btn-sm btn-danger' onclick=\"return confirm('Deseja excluir esta despesa?')\" title='Excluir'><i class='fas fa-trash'></i></a></td></tr>" for d in lista]) if lista else "<tr><td colspan='6' class='text-center text-muted'>Nenhuma despesa registrada.</td></tr>"}
                </tbody>
            </table>
        </div>
    </div>
    """)
    return render_template_string(html_page, active_tab='despesas', lista=lista)

@app.route('/despesas/editar/<int:id>', methods=['GET', 'POST'])
def editar_despesa(id):
    conn = get_db_connection()
    d = conn.execute("SELECT * FROM despesas WHERE id = ?", (id,)).fetchone()
    
    if request.method == 'POST':
        desc = request.form['descricao']
        cat = request.form['categoria']
        valor = float(request.form['valor'] or 0)
        conn.execute("UPDATE despesas SET descricao = ?, categoria = ?, valor = ? WHERE id = ?",
                     (desc, cat, valor, id))
        conn.commit()
        conn.close()
        flash("Despesa atualizada com sucesso!", "success")
        return redirect(url_for('despesas'))

    conn.close()
    html_page = BASE_TEMPLATE.replace("{% block content %}{% endblock %}", f"""
    <div class="header-custom"><h2><i class="fas fa-edit"></i> Editar Despesa (ID: {d['id']})</h2></div>
    <div class="card p-4">
        <form method="POST" class="row g-3">
            <div class="col-md-6"><label class="form-label">Descrição:</label><input type="text" class="form-control" name="descricao" value="{d['descricao'] or ''}" required></div>
            <div class="col-md-6"><label class="form-label">Categoria:</label>
                <select class="form-select" name="categoria">
                    <option value="Peças/Estoque" {'selected' if d['categoria'] == 'Peças/Estoque' else ''}>Peças/Estoque</option>
                    <option value="Impostos/Taxas" {'selected' if d['categoria'] == 'Impostos/Taxas' else ''}>Impostos/Taxas</option>
                    <option value="Internet/Telefone" {'selected' if d['categoria'] == 'Internet/Telefone' else ''}>Internet/Telefone</option>
                    <option value="Combustível/Transporte" {'selected' if d['categoria'] == 'Combustível/Transporte' else ''}>Combustível/Transporte</option>
                    <option value="Outros" {'selected' if d['categoria'] == 'Outros' else ''}>Outros</option>
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
    conn.execute("DELETE FROM despesas WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Despesa excluída com sucesso!", "success")
    return redirect(url_for('despesas'))

@app.route('/financeiro')
def financeiro():
    conn = get_db_connection()
    
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    cliente_filtro = request.args.get('cliente', '')
    servico_filtro = request.args.get('servico', '')

    clientes_disponiveis = conn.execute("SELECT DISTINCT cliente FROM ordens_servico WHERE cliente IS NOT NULL AND cliente != '' ORDER BY cliente").fetchall()
    servicos_disponiveis = conn.execute("SELECT DISTINCT servico FROM ordens_servico WHERE servico IS NOT NULL AND servico != '' ORDER BY servico").fetchall()

    query_os = "SELECT * FROM ordens_servico WHERE 1=1"
    params_os = []
    if data_inicio:
        query_os += " AND data_abertura >= ?"
        params_os.append(data_inicio)
    if data_fim:
        query_os += " AND data_abertura <= ?"
        params_os.append(data_fim)
    if cliente_filtro:
        query_os += " AND cliente = ?"
        params_os.append(cliente_filtro)
    if servico_filtro:
        query_os += " AND servico = ?"
        params_os.append(servico_filtro)
    
    os_filtradas = conn.execute(query_os, params_os).fetchall()

    query_esp = "SELECT * FROM despesas WHERE 1=1"
    params_esp = []
    if data_inicio:
        query_esp += " AND data_despesa >= ?"
        params_esp.append(data_inicio)
    if data_fim:
        query_esp += " AND data_despesa <= ?"
        params_esp.append(data_fim)
    
    despesas_filtradas = conn.execute(query_esp, params_esp).fetchall()

    query_bol = "SELECT SUM(valor) FROM boletos WHERE status = 'Pago'"
    params_bol = []
    if data_inicio:
        query_bol += " AND data_pagamento >= ?"
        params_bol.append(data_inicio)
    if data_fim:
        query_bol += " AND data_pagamento <= ?"
        params_bol.append(data_fim)
    if cliente_filtro:
        query_bol += " AND cliente = ?"
        params_bol.append(cliente_filtro)
    tot_pago = conn.execute(query_bol, params_bol).fetchone()[0] or 0.0

    query_rec = "SELECT SUM(valor) FROM boletos WHERE status != 'Pago'"
    params_rec = []
    if cliente_filtro:
        query_rec += " AND cliente = ?"
        params_rec.append(cliente_filtro)
    tot_receber = conn.execute(query_rec, params_rec).fetchone()[0] or 0.0

    tot_despesas = sum([d['valor'] for d in despesas_filtradas])
    saldo = tot_pago - tot_despesas

    ranking_clientes = conn.execute("""
        SELECT cliente, SUM(valor) as total_receita 
        FROM ordens_servico 
        WHERE cliente IS NOT NULL AND cliente != ''
        GROUP BY cliente 
        ORDER BY total_receita DESC LIMIT 5
    """).fetchall()

    ranking_servicos = conn.execute("""
        SELECT servico, SUM(valor) as total_receita, COUNT(*) as qtd
        FROM ordens_servico 
        WHERE servico IS NOT NULL AND servico != ''
        GROUP BY servico 
        ORDER BY total_receita DESC LIMIT 5
    """).fetchall()

    ranking_despesas = conn.execute("""
        SELECT categoria, SUM(valor) as total_despesa
        FROM despesas
        GROUP BY categoria
        ORDER BY total_despesa DESC LIMIT 5
    """).fetchall()

    conn.close()

    opt_clientes = "".join([f"<option value='{c['cliente']}' {'selected' if cliente_filtro == c['cliente'] else ''}>{c['cliente']}</option>" for c in clientes_disponiveis])
    opt_servicos = "".join([f"<option value='{s['servico']}' {'selected' if servico_filtro == s['servico'] else ''}>{s['servico']}</option>" for s in servicos_disponiveis])

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
                            {''.join([f"<tr><td>" + str(c['cliente']) + f"</td><td class='text-end fw-bold text-primary'>R$ " + f"{c['total_receita']:.2f}" + f"</td></tr>" for c in ranking_clientes]) if ranking_clientes else "<tr><td colspan='2' class='text-center text-muted'>Sem dados</td></tr>"}
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
                            {''.join([f"<tr><td>" + str(s['servico']) + f" <small class='text-muted'>({s['qtd']}x)</small></td><td class='text-end fw-bold text-success'>R$ " + f"{s['total_receita']:.2f}" + f"</td></tr>" for s in ranking_servicos]) if ranking_servicos else "<tr><td colspan='2' class='text-center text-muted'>Sem dados</td></tr>"}
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
                            {''.join([f"<tr><td>" + str(d['categoria']) + f"</td><td class='text-end fw-bold text-danger'>R$ " + f"{d['total_despesa']:.2f}" + f"</td></tr>" for d in ranking_despesas]) if ranking_despesas else "<tr><td colspan='2' class='text-center text-muted'>Sem dados</td></tr>"}
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