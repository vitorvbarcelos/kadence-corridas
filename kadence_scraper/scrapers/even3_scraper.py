import time
import hashlib
import re
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError

def gerar_hash_evento(titulo, data, local):
    """Gera hash único para evitar duplicatas"""
    conteudo = f"{titulo.lower().strip()}{data}{local.lower().strip()}"
    return hashlib.md5(conteudo.encode()).hexdigest()[:8]

def limpar_texto(texto):
    """Remove caracteres especiais e normaliza texto"""
    if not texto:
        return ""
    texto = re.sub(r'\s+', ' ', texto.strip())
    texto = texto.replace(',', ' ')
    return texto

def eh_evento_de_corrida(titulo, href=""):
    """Verifica se o evento é relacionado a corrida"""
    if not titulo:
        return False
    
    titulo_lower = titulo.lower()
    href_lower = href.lower() if href else ""
    
    # Palavras-chave que indicam corrida
    palavras_corrida = [
        'corrida', 'maratona', 'run', 'running', 'atletismo', 
        'cooper', 'caminhada', 'trote', 'meia maratona',
        '5k', '10k', '21k', '42k', 'km', 'trail',
        'night run', 'day run', 'street run'
    ]
    
    # Verifica no título
    for palavra in palavras_corrida:
        if palavra in titulo_lower:
            return True
    
    # Verifica na URL
    for palavra in palavras_corrida:
        if palavra in href_lower:
            return True
    
    return False

def processar_data_even3(data_str):
    """Processa datas no formato do Even3"""
    if not data_str:
        return None, None
    
    # Remove texto extra e normaliza
    data_limpa = re.sub(r'^[a-zA-Zç-]+,\s*', '', data_str.strip())  # Remove "domingo, "
    
    # Mapeia meses em português
    meses = {
        'janeiro': '01', 'fevereiro': '02', 'março': '03', 'abril': '04',
        'maio': '05', 'junho': '06', 'julho': '07', 'agosto': '08',
        'setembro': '09', 'outubro': '10', 'novembro': '11', 'dezembro': '12'
    }
    
    # Padrão: "7 de setembro de 2025"
    padrao = r'(\d{1,2})\s+de\s+([a-záéíóúç]+)\s+de\s+(\d{4})'
    match = re.search(padrao, data_limpa.lower())
    
    if match:
        dia = match.group(1).zfill(2)
        mes_texto = match.group(2)
        ano = match.group(3)
        
        mes_num = meses.get(mes_texto, '01')
        data_str_formatada = f"{dia}/{mes_num}/{ano}"
        
        try:
            data_obj = datetime.strptime(data_str_formatada, '%d/%m/%Y')
            return data_obj, data_str_formatada
        except ValueError:
            pass
    
    return None, data_str

def coletar_eventos_pagina(page):
    """Coleta eventos de corrida da seção 'Todos os eventos'"""
    eventos = []
    
    try:
        # Foca na seção "Todos os eventos" - os cards estão em divs específicas
        print("🔍 Procurando eventos na seção 'Todos os eventos'...")
        
        # Seletor mais específico baseado no HTML real
        cards = page.query_selector_all(".col-xl-3.col-lg-4.col-md-6.col-sm-12 .card")
        
        print(f"📦 Encontrados {len(cards)} cards para análise")
        
        for i, card in enumerate(cards):
            try:
                # Título
                titulo_el = card.query_selector("h5.card-title")
                titulo = limpar_texto(titulo_el.inner_text()) if titulo_el else ""
                
                # Link para verificar se é corrida
                link_el = card.query_selector("a.stretched-link")
                href = link_el.get_attribute("href") if link_el else ""
                
                # Filtra só eventos de corrida
                if not eh_evento_de_corrida(titulo, href):
                    continue
                
                # Data - busca por elementos com ícone de calendário
                data_el = card.query_selector("span:has(i.fa-calendar-day)")
                if not data_el:
                    data_el = card.query_selector(".card-text span")
                
                data_raw = data_el.inner_text().strip() if data_el else ""
                
                data_obj, data_formatada = processar_data_even3(data_raw)
                if not data_obj:
                    continue
                
                # Só eventos futuros
                if data_obj < datetime.now():
                    continue
                
                # Local - busca por elementos com ícone de localização
                local_el = card.query_selector("span:has(i.fa-map-marker-alt)")
                if local_el:
                    local_text = local_el.inner_text().strip()
                    # Remove o ícone do texto e limpa
                    local = re.sub(r'^\s*[^\w\s]*\s*', '', local_text).strip()
                    local = limpar_texto(local)
                else:
                    local = "Local não informado"
                
                # Link completo
                link = href if href and href.startswith("http") else f"https://even3.com.br{href}" if href else ""
                
                # Validações
                if len(titulo.strip()) < 3:
                    continue
                
                # Hash para deduplicação
                evento_hash = gerar_hash_evento(titulo, data_formatada, local)
                
                eventos.append({
                    "titulo": titulo,
                    "data": data_formatada,
                    "local": local, 
                    "link": link,
                    "hash": evento_hash,
                    "fonte": "Even3",
                    "data_obj": data_obj
                })
                
                # Debug das primeiras 3 corridas encontradas
                if len(eventos) <= 3:
                    print(f"   ✅ Corrida {len(eventos)}: {titulo[:40]}... | {data_formatada} | {local[:30]}...")
                
            except Exception as e:
                continue
        
        print(f"🎯 Total de corridas identificadas: {len(eventos)}")
                
    except Exception as e:
        print(f"   ⚠️ Erro ao coletar eventos: {str(e)[:50]}...")
    
    return eventos

def carregar_todos_eventos_even3(page, max_cliques=30):
    """Carrega todos os eventos clicando em 'Ver mais' na seção 'Todos os eventos'"""
    print("🔄 Carregando todos os eventos da seção 'Todos os eventos'...")
    
    cliques_realizados = 0
    cliques_sem_efeito = 0
    
    while cliques_realizados < max_cliques and cliques_sem_efeito < 3:
        try:
            # Scroll para a seção "Todos os eventos" (no final da página)
            try:
                secao_todos = page.query_selector("h2:has-text('Todos os eventos')")
                if secao_todos:
                    secao_todos.scroll_into_view_if_needed()
                    time.sleep(1)
            except:
                pass
            
            # Conta eventos antes do clique
            cards_antes = len(page.query_selector_all(".card"))
            
            # Procura pelo botão "Ver mais" - seletores baseados no HTML real
            seletores_ver_mais = [
                "button:has-text('Ver mais')",
                "button.btn-primary:has-text('Ver mais')",
                "button[ng-click='carregarMaisEventos()']",
                ".btn.btn-primary.btn-block:has-text('Ver mais')",
                "[data-loading-text='Aguarde']"
            ]
            
            botao_ver_mais = None
            for seletor in seletores_ver_mais:
                try:
                    botao_ver_mais = page.query_selector(seletor)
                    if botao_ver_mais and botao_ver_mais.is_visible() and not botao_ver_mais.is_disabled():
                        break
                except:
                    continue
            
            if not botao_ver_mais:
                print(f"   🔍 Botão 'Ver mais' não encontrado - fim dos eventos")
                break
            
            # Clica no botão
            print(f"   👉 Clique {cliques_realizados + 1} - Aguardando novos eventos...")
            botao_ver_mais.click()
            cliques_realizados += 1
            
            # Aguarda AngularJS carregar novos eventos
            time.sleep(4)
            
            # Verifica se novos eventos foram adicionados
            cards_depois = len(page.query_selector_all(".card"))
            
            if cards_depois > cards_antes:
                cliques_sem_efeito = 0
                print(f"   📈 {cards_depois} eventos total (+{cards_depois - cards_antes} novos)")
            else:
                cliques_sem_efeito += 1
                print(f"   ⏳ Sem novos eventos ({cliques_sem_efeito}/3)")
            
        except Exception as e:
            print(f"   ⚠️ Erro ao clicar 'Ver mais': {str(e)[:50]}...")
            cliques_sem_efeito += 1
            time.sleep(2)
    
    total_final = len(page.query_selector_all(".card"))
    print(f"🏁 Carregamento finalizado: {total_final} eventos | {cliques_realizados} cliques realizados")
    return total_final

def extrair_even3(max_tentativas=3):
    """Extrai eventos de corrida do Even3"""
    eventos = []
    
    for tentativa in range(max_tentativas):
        try:
            print(f"🔎 Even3 - Tentativa {tentativa + 1}/{max_tentativas}")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()
                
                url = "https://www.even3.com.br/eventos-online/saude-e-bem-estar/"
                
                try:
                    print("📄 Carregando Even3...")
                    page.goto(url, timeout=60000)
                    
                    # Aguarda a página carregar completamente
                    time.sleep(5)
                    
                    # Carrega todos os eventos clicando em "Ver mais"
                    total_cards = carregar_todos_eventos_even3(page, max_cliques=30)
                    
                    # Agora coleta todas as corridas de uma vez
                    print(f"🔄 Processando {total_cards} eventos em busca de corridas...")
                    eventos = coletar_eventos_pagina(page)
                    
                    browser.close()
                    
                    if eventos:
                        # Remove duplicatas internas
                        eventos_unicos = {}
                        for evento in eventos:
                            hash_evento = evento['hash']
                            if hash_evento not in eventos_unicos:
                                eventos_unicos[hash_evento] = evento
                        
                        eventos_finais = list(eventos_unicos.values())
                        eventos_finais.sort(key=lambda x: x['data_obj'])
                        
                        duplicatas = len(eventos) - len(eventos_finais)
                        
                        print(f"✅ Even3: {len(eventos_finais)} corridas únicas coletadas")
                        if duplicatas > 0:
                            print(f"🔄 {duplicatas} duplicatas internas removidas")
                        
                        return eventos_finais
                    else:
                        print("⚠️ Nenhuma corrida encontrada")
                        
                except TimeoutError:
                    print(f"❌ Timeout na tentativa {tentativa + 1}")
                    browser.close()
                    continue
                    
        except Exception as e:
            print(f"❌ Erro geral na tentativa {tentativa + 1}: {str(e)[:80]}...")
            if tentativa == max_tentativas - 1:
                print("💀 Even3 falhou após todas as tentativas")
            continue
    
    return eventos