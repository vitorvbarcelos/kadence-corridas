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

def eh_evento_de_corrida_minhas_inscricoes(titulo, categoria=""):
    """Verifica se o evento é relacionado a corrida"""
    if not titulo:
        return False
    
    titulo_lower = titulo.lower()
    categoria_lower = categoria.lower() if categoria else ""
    
    # Palavras-chave que indicam corrida
    palavras_corrida = [
        'corrida', 'maratona', 'run', 'running', 'atletismo', 
        'cooper', 'caminhada', 'trote', 'meia maratona',
        '5k', '10k', '21k', '42k', 'km', 'trail',
        'night run', 'day run', 'street run', 'rustica'
    ]
    
    # Categorias que indicam corrida
    categorias_corrida = [
        'corrida de rua', 'trail run', 'ultramaratona', 
        'meia maratona', 'evento de corrida', 'corridas de montanha'
    ]
    
    # Verifica na categoria primeiro (mais confiável)
    for cat in categorias_corrida:
        if cat in categoria_lower:
            return True
    
    # Verifica no título
    for palavra in palavras_corrida:
        if palavra in titulo_lower:
            return True
    
    return False

def processar_data_minhas_inscricoes(data_str):
    """Processa datas do formato: '09/08/2025'"""
    if not data_str:
        return None, None
    
    # Remove ícones e espaços extras
    data_limpa = re.sub(r'<[^>]+>', '', data_str)  # Remove tags HTML
    data_limpa = data_limpa.strip()
    
    # Padrão: "09/08/2025"
    padrao = r'(\d{2})/(\d{2})/(\d{4})'
    match = re.search(padrao, data_limpa)
    
    if match:
        dia, mes, ano = match.groups()
        data_str_formatada = f"{dia}/{mes}/{ano}"
        
        try:
            data_obj = datetime.strptime(data_str_formatada, '%d/%m/%Y')
            return data_obj, data_str_formatada
        except ValueError:
            pass
    
    return None, data_str

def navegar_paginas_minhas_inscricoes(page, max_paginas=16):
    """Navega pelas páginas do Minhas Inscrições"""
    todos_eventos = []
    
    for pagina_atual in range(1, max_paginas + 1):
        try:
            print(f"   📄 Processando página {pagina_atual}")
            
            if pagina_atual == 1:
                # Primeira página já está carregada
                print(f"   ✅ Página 1 já carregada")
            else:
                # Navega para próxima página
                try:
                    # Procura pelo link da página específica
                    link_pagina = page.query_selector(f"a[href*='pagina={pagina_atual}']")
                    if link_pagina and link_pagina.is_visible():
                        link_pagina.click()
                        time.sleep(4)  # Aguarda carregar (AJAX)
                    else:
                        print(f"   ❌ Link da página {pagina_atual} não encontrado")
                        break
                except Exception as e:
                    print(f"   ⚠️ Erro ao navegar para página {pagina_atual}: {str(e)[:50]}...")
                    break
            
            # Aguarda os cards carregarem
            try:
                page.wait_for_selector(".thumbnail.card-default", timeout=10000)
            except TimeoutError:
                print(f"   ⚠️ Página {pagina_atual}: Cards não carregaram")
                continue
            
            # Coleta eventos da página atual
            eventos_pagina = coletar_eventos_pagina_minhas_inscricoes(page, pagina_atual)
            
            if eventos_pagina:
                todos_eventos.extend(eventos_pagina)
                print(f"   ✅ Página {pagina_atual}: {len(eventos_pagina)} corridas coletadas")
            else:
                print(f"   ⚠️ Página {pagina_atual}: Nenhuma corrida encontrada")
            
            # Pequena pausa entre páginas
            time.sleep(2)
                
        except Exception as e:
            print(f"   ❌ Erro na página {pagina_atual}: {str(e)[:50]}...")
            continue
    
    return todos_eventos

def coletar_eventos_pagina_minhas_inscricoes(page, pagina_num):
    """Coleta eventos de corrida de uma página do Minhas Inscrições"""
    eventos = []
    
    try:
        # Seleciona todos os cards de evento
        cards = page.query_selector_all(".thumbnail.card-default")
        
        for i, card in enumerate(cards):
            try:
                # Título
                titulo_el = card.query_selector(".titulo-destaque")
                titulo = limpar_texto(titulo_el.inner_text()) if titulo_el else ""
                
                if not titulo:
                    continue
                
                # Data
                data_el = card.query_selector("p:has(i.fa-calendar-alt)")
                data_raw = ""
                if data_el:
                    data_raw = limpar_texto(data_el.inner_text())
                else:
                    continue
                
                data_obj, data_formatada = processar_data_minhas_inscricoes(data_raw)
                if not data_obj:
                    continue
                
                # Só eventos futuros
                if data_obj < datetime.now():
                    continue
                
                # Local
                local_el = card.query_selector("p:has(i.fa-map-marker) span")
                local = limpar_texto(local_el.inner_text()) if local_el else "Local não informado"
                
                # Categoria (último <p> do card)
                categoria_els = card.query_selector_all("p")
                categoria = ""
                for p in categoria_els:
                    texto_p = limpar_texto(p.inner_text())
                    # Se não tem ícone e não é data/local, provavelmente é categoria
                    if not p.query_selector("i") and texto_p and "/" not in texto_p:
                        categoria = texto_p
                        break
                
                # Verifica se é evento de corrida
                if not eh_evento_de_corrida_minhas_inscricoes(titulo, categoria):
                    continue
                
                # Link
                link_el = card.query_selector("a.btn.btn-warning")
                if not link_el:
                    link_el = card.query_selector("a[href*='ClickEventos']")
                
                link = ""
                if link_el:
                    href = link_el.get_attribute("href")
                    if href:
                        link = href if href.startswith("http") else f"https://minhasinscricoes.com.br{href}"
                
                # Validações básicas
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
                    "fonte": "MinhasInscricoes",
                    "data_obj": data_obj,
                    "categoria": categoria
                })
                
                # Mostra detalhes dos primeiros 3 eventos
                if len(eventos) <= 3:
                    print(f"   ✅ Evento {len(eventos)}: {titulo[:35]}... | {data_formatada} | {local[:25]}...")
                
            except Exception as e:
                continue
                
    except Exception as e:
        print(f"   ⚠️ Erro ao coletar página {pagina_num}: {str(e)[:50]}...")
    
    return eventos

def extrair_minhas_inscricoes(max_tentativas=3):
    """Extrai eventos de corrida do Minhas Inscrições"""
    eventos = []
    
    for tentativa in range(max_tentativas):
        try:
            print(f"🔎 Minhas Inscrições - Tentativa {tentativa + 1}/{max_tentativas}")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # URL do calendário com filtro para corridas
                url = "https://minhasinscricoes.com.br/pt-br/calendario"
                
                try:
                    print("📄 Carregando Minhas Inscrições...")
                    page.goto(url, timeout=60000)
                    
                    # Aguarda a página carregar completamente
                    time.sleep(5)
                    
                    # Aguarda os cards aparecerem
                    try:
                        page.wait_for_selector(".thumbnail.card-default", timeout=20000)
                    except TimeoutError:
                        print("   ⚠️ Cards não carregaram no tempo esperado")
                        browser.close()
                        continue
                    
                    # Verifica se há filtros ativos e aplicar se necessário
                    try:
                        # Pode aplicar filtros aqui se necessário
                        print("   🔧 Verificando se precisa aplicar filtros...")
                        # Por enquanto vamos pegar todos os eventos e filtrar depois
                    except Exception as e:
                        print(f"   ⚠️ Erro ao aplicar filtros: {str(e)[:50]}...")
                    
                    # Navega por todas as páginas
                    eventos = navegar_paginas_minhas_inscricoes(page, max_paginas=16)
                    
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
                        
                        print(f"✅ Minhas Inscrições: {len(eventos_finais)} corridas únicas coletadas")
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
                print("💀 Minhas Inscrições falhou após todas as tentativas")
            continue
    
    return eventos