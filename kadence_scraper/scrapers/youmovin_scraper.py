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

def processar_data_youmovin(data_str):
    """Processa data do formato YouMovin: '09/08/2025 14:30' -> '09/08/2025'"""
    if not data_str:
        return None, None
    
    # Remove horário se presente
    data_limpa = data_str.split(' ')[0].strip()
    
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

def eh_evento_de_corrida_youmovin(titulo, categoria=""):
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
    
    # Verifica na categoria primeiro (mais confiável)
    if 'corrida de rua' in categoria_lower or 'aventura' in categoria_lower:
        return True
    
    # Verifica no título
    for palavra in palavras_corrida:
        if palavra in titulo_lower:
            return True
    
    return False

def navegar_paginas_youmovin(page, max_paginas=10):
    """Navega pelas páginas do YouMovin usando paginação"""
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
                    url_pagina = f"https://www.youmovin.com.br/calendario-de-eventos/{pagina_atual}?filtro=S"
                    page.goto(url_pagina, timeout=30000)
                    time.sleep(3)
                except Exception as e:
                    print(f"   ⚠️ Erro ao navegar para página {pagina_atual}: {str(e)[:50]}...")
                    break
            
            # Aguarda os cards carregarem
            try:
                page.wait_for_selector(".content ul.calendario_tb", timeout=10000)
            except TimeoutError:
                print(f"   ⚠️ Página {pagina_atual}: Cards não carregaram")
                continue
            
            # Coleta eventos da página atual
            eventos_pagina = coletar_eventos_pagina_youmovin(page, pagina_atual)
            
            if eventos_pagina:
                todos_eventos.extend(eventos_pagina)
                print(f"   ✅ Página {pagina_atual}: {len(eventos_pagina)} corridas coletadas")
            else:
                print(f"   ⚠️ Página {pagina_atual}: Nenhuma corrida encontrada")
            
            # Verifica se há próxima página
            try:
                proximo_link = page.query_selector("a:has-text('Próxima')")
                if not proximo_link or not proximo_link.is_visible():
                    print(f"   🏁 Não há mais páginas")
                    break
            except:
                break
            
            # Pequena pausa entre páginas
            time.sleep(2)
                
        except Exception as e:
            print(f"   ❌ Erro na página {pagina_atual}: {str(e)[:50]}...")
            continue
    
    return todos_eventos

def coletar_eventos_pagina_youmovin(page, pagina_num):
    """Coleta eventos de corrida de uma página do YouMovin"""
    eventos = []
    
    try:
        # Seleciona todos os cards de evento
        cards = page.query_selector_all(".content")
        
        for i, card in enumerate(cards):
            try:
                # Verifica se é um card de evento válido
                calendar_tb = card.query_selector("ul.calendario_tb")
                if not calendar_tb:
                    continue
                
                # Título - busca pelo span com onclick
                titulo_el = card.query_selector(".t_calendario span[onclick]")
                titulo = ""
                link = ""
                
                if titulo_el:
                    titulo = limpar_texto(titulo_el.inner_text())
                    onclick_attr = titulo_el.get_attribute("onclick")
                    if onclick_attr:
                        # Extrai URL do onclick: document.location.href='URL'
                        match = re.search(r"document\.location\.href='([^']+)'", onclick_attr)
                        if match:
                            url = match.group(1)
                            link = url if url.startswith("http") else f"https://www.youmovin.com.br{url}"
                
                if not titulo:
                    continue
                
                # Busca informações nos elementos da tabela (so_desktop)
                info_elements = card.query_selector_all(".so_desktop li")
                
                data_raw = ""
                categoria = ""
                modalidade = ""
                local = "Local não informado"
                
                # Processa elementos de informação (ignora headers)
                for j, info_el in enumerate(info_elements):
                    try:
                        texto = limpar_texto(info_el.inner_text())
                        
                        # Pula headers
                        if texto in ["Data Hora", "Categoria", "Modalidade", "Local"]:
                            continue
                        
                        # Primeira info válida é a data
                        if not data_raw and "/" in texto:
                            data_raw = texto
                        # Segunda info é categoria
                        elif not categoria and "corrida" in texto.lower():
                            categoria = texto
                        # Terceira info é modalidade (contém KM geralmente)
                        elif not modalidade and ("km" in texto.lower() or "k" in texto.lower()):
                            modalidade = texto
                        # Local geralmente contém " - " (cidade - estado)
                        elif " - " in texto and not local.endswith(" - RS"):
                            local = texto
                        
                    except Exception:
                        continue
                
                # Verifica se é evento de corrida
                if not eh_evento_de_corrida_youmovin(titulo, categoria):
                    continue
                
                # Processa a data
                data_obj, data_formatada = processar_data_youmovin(data_raw)
                if not data_obj:
                    continue
                
                # Só eventos futuros
                if data_obj < datetime.now():
                    continue
                
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
                    "fonte": "YouMovin",
                    "data_obj": data_obj,
                    "categoria": categoria,
                    "modalidade": modalidade
                })
                
                # Mostra detalhes dos primeiros 3 eventos
                if len(eventos) <= 3:
                    print(f"   ✅ Evento {len(eventos)}: {titulo[:35]}... | {data_formatada} | {local[:25]}...")
                
            except Exception as e:
                continue
                
    except Exception as e:
        print(f"   ⚠️ Erro ao coletar página {pagina_num}: {str(e)[:50]}...")
    
    return eventos

def extrair_youmovin(max_tentativas=3):
    """Extrai eventos de corrida do YouMovin"""
    eventos = []
    
    for tentativa in range(max_tentativas):
        try:
            print(f"🔎 YouMovin - Tentativa {tentativa + 1}/{max_tentativas}")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # URL do calendário com filtro para corridas (categoria=1)
                url = "https://www.youmovin.com.br/calendario-de-eventos?categoria=1"
                
                try:
                    print("📄 Carregando YouMovin...")
                    page.goto(url, timeout=60000)
                    
                    # Aguarda a página carregar completamente
                    time.sleep(5)
                    
                    # Aguarda os cards aparecerem
                    try:
                        page.wait_for_selector(".content ul.calendario_tb", timeout=20000)
                    except TimeoutError:
                        print("   ⚠️ Cards não carregaram no tempo esperado")
                        browser.close()
                        continue
                    
                    # Navega por todas as páginas
                    eventos = navegar_paginas_youmovin(page, max_paginas=10)
                    
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
                        
                        print(f"✅ YouMovin: {len(eventos_finais)} corridas únicas coletadas")
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
                print("💀 YouMovin falhou após todas as tentativas")
            continue
    
    return eventos