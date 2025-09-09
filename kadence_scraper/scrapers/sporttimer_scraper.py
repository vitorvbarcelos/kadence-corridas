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
    texto = texto.replace(',', ' ')  # Remove vírgulas para não quebrar CSV
    return texto

def processar_data_sporttimer(titulo):
    """Extrai e processa data do título SportTimer: '12/10 – Título' -> '12/10/2025'"""
    if not titulo:
        return None, None, titulo
    
    # Regex para capturar data no formato DD/MM no início do título
    match = re.match(r'^(\d{1,2})/(\d{1,2})\s*[–-]\s*(.+)', titulo)
    if not match:
        return None, None, titulo
    
    try:
        dia = match.group(1).zfill(2)
        mes = match.group(2).zfill(2)
        titulo_limpo = match.group(3).strip()
        
        # Assume ano atual ou próximo
        ano_atual = datetime.now().year
        data_str_formatada = f"{dia}/{mes}/{ano_atual}"
        
        try:
            data_obj = datetime.strptime(data_str_formatada, '%d/%m/%Y')
            # Se a data já passou, assume ano seguinte
            if data_obj < datetime.now():
                data_obj = datetime.strptime(f"{dia}/{mes}/{ano_atual + 1}", '%d/%m/%Y')
                data_str_formatada = f"{dia}/{mes}/{ano_atual + 1}"
            
            return data_obj, data_str_formatada, titulo_limpo
        except ValueError:
            pass
    except:
        pass
    
    return None, titulo, titulo

def extrair_detalhes_evento(browser, url_evento):
    """Entra na página do evento em nova aba e extrai local detalhado"""
    local_detalhado = "Local não informado"
    
    try:
        print(f"     🔍 Acessando evento: {url_evento}")
        # Cria nova página/aba para não perder a principal
        page_evento = browser.new_page()
        page_evento.goto(url_evento, timeout=30000)
        time.sleep(3)  # Aguarda carregamento
        
        # Busca pela lista com ícones que contém as informações do evento
        # Padrão: <li><i class="fas fa-check"></i>Cidade: São Luis de Montes Belos Goiás</li>
        cidade_items = page_evento.query_selector_all("li:has(i.fas.fa-check)")
        
        for item in cidade_items:
            texto = limpar_texto(item.inner_text())
            
            # Procura por padrões de cidade
            if "cidade:" in texto.lower():
                # Extrai depois de "Cidade:"
                cidade_match = re.search(r'cidade:\s*(.+)', texto, re.IGNORECASE)
                if cidade_match:
                    local_detalhado = cidade_match.group(1).strip()
                    break
            elif "local:" in texto.lower():
                # Extrai depois de "Local:"
                local_match = re.search(r'local:\s*(.+)', texto, re.IGNORECASE)
                if local_match:
                    local_detalhado = local_match.group(1).strip()
                    break
        
        # Se não encontrou na lista, tenta outras estratégias
        if local_detalhado == "Local não informado":
            # Busca em qualquer texto que mencione cidades conhecidas + estado
            page_text = page_evento.inner_text()
            
            # Padrões de cidades do Centro-Oeste
            padroes_cidade = [
                r'([A-ZÁÊÇÕ\s]+(?:Goiás|Goias|GO))',
                r'([A-ZÁÊÇÕ\s]+(?:Minas Gerais|MG))',
                r'([A-ZÁÊÇÕ\s]+(?:Brasília|DF))',
                r'([A-ZÁÊÇÕ\s]+(?:Mato Grosso|MT))',
                r'([A-ZÁÊÇÕ\s]+(?:Mato Grosso do Sul|MS))',
            ]
            
            for padrao in padroes_cidade:
                match = re.search(padrao, page_text, re.IGNORECASE)
                if match:
                    possivel_local = match.group(1).strip()
                    if len(possivel_local) > 5:  # Validação básica
                        local_detalhado = possivel_local
                        break
        
        print(f"     ✅ Local extraído: {local_detalhado}")
        
        # IMPORTANTE: Fecha a página do evento para não consumir memória
        page_evento.close()
        
        return local_detalhado
        
    except Exception as e:
        print(f"     ⚠️ Erro ao extrair detalhes: {str(e)[:50]}...")
        try:
            page_evento.close()  # Garante que fecha mesmo com erro
        except:
            pass
        return "Região Centro-Oeste"

def coletar_eventos_sporttimer_detalhado(page, browser):
    """Coleta eventos do SportTimer entrando em cada um para detalhes"""
    eventos = []
    
    try:
        # Scroll para carregar todos os eventos
        print("   🔄 Carregando todos os eventos da página principal...")
        for i in range(5):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
        
        # Seleciona todos os cards de evento
        cards = page.query_selector_all(".col-sm-4.col-lg-3")
        print(f"   📦 {len(cards)} cards encontrados")
        
        for i, card in enumerate(cards):
            try:
                print(f"   📋 Processando evento {i+1}/{len(cards)}")
                
                # Link e título do evento
                link_el = card.query_selector("a")
                titulo_el = card.query_selector(".thumb-info-inner h2")
                
                if not link_el or not titulo_el:
                    continue
                
                titulo_completo = limpar_texto(titulo_el.inner_text())
                if not titulo_completo or len(titulo_completo) < 5:
                    continue
                
                # Extrai data e limpa título
                data_obj, data_formatada, titulo_limpo = processar_data_sporttimer(titulo_completo)
                if not data_obj:
                    continue
                
                # Só eventos futuros
                if data_obj < datetime.now():
                    continue
                
                # URL do evento
                href = link_el.get_attribute("href")
                if not href:
                    continue
                    
                url_evento = href if href.startswith("http") else f"https://www.sporttimer.com.br{href}"
                
                # Categoria/modalidade
                categoria_el = card.query_selector(".thumb-info-type")
                categoria = limpar_texto(categoria_el.inner_text()) if categoria_el else "Corrida de Rua"
                
                # AQUI É A MAGIA: Entra no evento para extrair local detalhado
                local_detalhado = extrair_detalhes_evento(browser, url_evento)
                
                # Validações básicas
                if len(titulo_limpo.strip()) < 5:
                    continue
                
                # Hash para deduplicação
                evento_hash = gerar_hash_evento(titulo_limpo, data_formatada, local_detalhado)
                
                eventos.append({
                    "titulo": titulo_limpo,
                    "data": data_formatada,
                    "local": local_detalhado,
                    "link": url_evento,
                    "hash": evento_hash,
                    "fonte": "SportTimer",
                    "data_obj": data_obj,
                    "categoria": categoria.title(),
                    "modalidade": categoria.title()
                })
                
                print(f"   ✅ Evento coletado: {titulo_limpo[:30]}... | {data_formatada} | {local_detalhado[:20]}...")
                
                # Pequena pausa para não sobrecarregar o servidor
                time.sleep(1)
                
            except Exception as e:
                print(f"   ❌ Erro no evento {i+1}: {str(e)[:50]}...")
                continue
        
        print(f"   🎯 Total de eventos válidos coletados: {len(eventos)}")
                
    except Exception as e:
        print(f"   ⚠️ Erro geral ao coletar eventos: {str(e)[:50]}...")
    
    return eventos

def extrair_sporttimer(max_tentativas=3):
    """Extrai eventos de corrida do SportTimer.com.br com detalhes completos"""
    eventos = []
    
    for tentativa in range(max_tentativas):
        try:
            print(f"🔎 SportTimer.com.br (DETALHADO) - Tentativa {tentativa + 1}/{max_tentativas}")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # URL da página principal do SportTimer
                url = "https://www.sporttimer.com.br/"
                
                try:
                    print("📄 Carregando SportTimer.com.br...")
                    page.goto(url, timeout=60000)
                    
                    # Aguarda a página carregar completamente
                    time.sleep(5)
                    
                    # Aguarda os cards aparecerem
                    try:
                        page.wait_for_selector(".col-sm-4.col-lg-3", timeout=20000)
                    except TimeoutError:
                        print("   ⚠️ Cards não carregaram no tempo esperado")
                        browser.close()
                        continue
                    
                    # Coleta todos os eventos COM DETALHES
                    print(f"🔄 Processando eventos com detalhes completos...")
                    eventos = coletar_eventos_sporttimer_detalhado(page, browser)
                    
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
                        
                        print(f"✅ SportTimer.com.br: {len(eventos_finais)} eventos únicos coletados")
                        if duplicatas > 0:
                            print(f"🔄 {duplicatas} duplicatas internas removidas")
                        
                        return eventos_finais
                    else:
                        print("⚠️ Nenhum evento encontrado")
                        
                except TimeoutError:
                    print(f"❌ Timeout na tentativa {tentativa + 1}")
                    browser.close()
                    continue
                    
        except Exception as e:
            print(f"❌ Erro geral na tentativa {tentativa + 1}: {str(e)[:80]}...")
            if tentativa == max_tentativas - 1:
                print("💀 SportTimer.com.br falhou após todas as tentativas")
            continue
    
    return eventos