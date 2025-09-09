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

def processar_data_atletis(data_str):
    """Processa diferentes formatos de data do Atletis"""
    if not data_str:
        return None, None
    
    # Remove texto extra e normaliza
    data_limpa = data_str.strip()
    
    # Mapeia meses em português
    meses = {
        'janeiro': '01', 'fevereiro': '02', 'março': '03', 'abril': '04',
        'maio': '05', 'junho': '06', 'julho': '07', 'agosto': '08',
        'setembro': '09', 'outubro': '10', 'novembro': '11', 'dezembro': '12'
    }
    
    # Padrão: "07 Junho 2026"
    padrao = r'(\d{1,2})\s+([a-záéíóúç]+)\s+(\d{4})'
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

def navegar_paginas_atletis(page, max_paginas=96):
    """Navega pelas páginas do Atletis usando paginação numérica - OTIMIZADO"""
    todos_eventos = []
    
    for pagina_atual in range(1, max_paginas + 1):
        try:
            print(f"   📄 Página {pagina_atual}")
            
            # URL da página específica
            if pagina_atual == 1:
                url_pagina = "https://www.atletis.com.br/eventos"
            else:
                url_pagina = f"https://www.atletis.com.br/eventos/{pagina_atual}"
            
            page.goto(url_pagina, timeout=30000)
            
            # Aguarda apenas o essencial - DOM estar pronto
            try:
                page.wait_for_selector(".event-card", timeout=8000)
            except TimeoutError:
                print(f"   ❌ Página {pagina_atual}: Sem eventos")
                break  # Se não tem cards, chegou ao fim
            
            # Coleta eventos da página atual
            eventos_pagina = coletar_eventos_pagina_atletis(page)
            
            if eventos_pagina:
                todos_eventos.extend(eventos_pagina)
                print(f"   ✅ Página {pagina_atual}: {len(eventos_pagina)} eventos")
            else:
                print(f"   ⚠️ Página {pagina_atual}: Vazia - finalizando")
                break  # Se não tem eventos, provavelmente chegou ao fim
            
            # Pausa mínima entre páginas
            time.sleep(0.5)
                
        except Exception as e:
            print(f"   ❌ Erro página {pagina_atual}: {str(e)[:30]}...")
            continue
    
    return todos_eventos

def coletar_eventos_pagina_atletis(page):
    """Coleta eventos de uma página do Atletis - OTIMIZADO"""
    eventos = []
    
    try:
        # Pega os cards - seletor direto
        cards = page.query_selector_all(".event-card")
        
        if not cards:
            return eventos
        
        for i, card in enumerate(cards):
            try:
                # Título
                titulo_el = card.query_selector(".event-card-title")
                titulo = limpar_texto(titulo_el.inner_text()) if titulo_el else ""
                
                if not titulo or len(titulo) < 3:
                    continue
                
                # Link
                link_el = card.query_selector("a[href*='evento']")
                if not link_el:
                    link_el = card.query_selector(".event-card-image a")
                if not link_el:
                    link_el = card.query_selector(".event-card-body a")
                
                link = ""
                if link_el:
                    href = link_el.get_attribute("href")
                    if href:
                        link = href if href.startswith("http") else f"https://www.atletis.com.br{href}"
                
                # Busca informações nos event-card-info
                info_elements = card.query_selector_all(".event-card-info")
                
                data_raw = ""
                local = "Local não informado"
                
                # Estratégia pela posição dos elementos
                for j, info_el in enumerate(info_elements):
                    try:
                        # Primeira info é a data
                        if j == 0:
                            span_el = info_el.query_selector("span")
                            if span_el:
                                data_raw = span_el.inner_text().strip()
                        
                        # Segunda info é o local
                        elif j == 1:
                            local = limpar_texto(info_el.inner_text())
                            
                    except Exception:
                        continue
                
                # Processa a data
                data_obj, data_formatada = processar_data_atletis(data_raw)
                if not data_obj:
                    continue
                
                # Só eventos futuros
                if data_obj < datetime.now():
                    continue
                
                # Hash para deduplicação
                evento_hash = gerar_hash_evento(titulo, data_formatada, local)
                
                eventos.append({
                    "titulo": titulo,
                    "data": data_formatada,
                    "local": local,
                    "link": link,
                    "hash": evento_hash,
                    "fonte": "Atletis",
                    "data_obj": data_obj
                })
                
            except Exception as e:
                continue
    
    except Exception as e:
        print(f"   ⚠️ Erro ao coletar página: {str(e)[:30]}...")
    
    return eventos

def extrair_atletis(max_tentativas=3):
    """Extrai eventos do Atletis - VERSÃO OTIMIZADA"""
    eventos = []
    
    for tentativa in range(max_tentativas):
        try:
            print(f"🔎 Atletis (OTIMIZADO) - Tentativa {tentativa + 1}/{max_tentativas}")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # 🚀 OTIMIZAÇÕES DE PERFORMANCE
                # Bloqueia recursos pesados desnecessários
                page.route("**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2,ttf,eot}", lambda route: route.abort())
                page.route("**/*.{css}", lambda route: route.abort())  # CSS não é necessário para dados
                page.route("**/analytics**", lambda route: route.abort())
                page.route("**/gtag**", lambda route: route.abort())
                page.route("**/google-analytics**", lambda route: route.abort())
                page.route("**/facebook.net**", lambda route: route.abort())
                
                # Configurações de performance
                page.set_extra_http_headers({
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
                    "Cache-Control": "no-cache"
                })
                
                try:
                    print("📄 Carregando Atletis (modo otimizado)...")
                    
                    # Navega por todas as páginas
                    eventos = navegar_paginas_atletis(page, max_paginas=96)
                    
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
                        
                        print(f"✅ Atletis: {len(eventos_finais)} eventos únicos coletados")
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
                print("💀 Atletis falhou após todas as tentativas")
            continue
    
    return eventos