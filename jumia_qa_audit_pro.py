import flet as ft
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import sys
import locale
import threading
from datetime import datetime
import time
from urllib.parse import urlparse
import math
import re
import subprocess

def main(page: ft.Page):
    # --- 1. Configuration de la page Flet ---
    page.title = "Jumia Smart Scraper Pro"
    page.theme_mode = ft.ThemeMode.DARK 
    page.window_width = 900 
    page.window_height = 800
    page.window_min_width = 600
    page.window_min_height = 700
    page.padding = 20
    # Icône de la fenêtre (Optionnel, peut être ignoré si l'URL ne répond pas)
    page.window_icon = "https://www.jumia.sn/assets_he/favicon.adbd556a.svg"
    
    # --- Variables d'État ---
    analysis_result = {"base_url": "", "total_pages": 1, "total_products": 0}
    
    # --- 2. Textes & Langue (Version Complète) ---
    def get_texts():
        is_fr = False
        try:
            lang = locale.getdefaultlocale()[0]
            if lang and lang.lower().startswith('fr'):
                is_fr = True
            if not is_fr and sys.platform == 'win32':
                import ctypes
                user_lang = ctypes.windll.kernel32.GetUserDefaultUILanguage()
                if (user_lang & 0xFF) == 0x0C:
                    is_fr = True
        except:
            is_fr = True 

        if is_fr:
            return {
                'title': "Jumia Smart Scraper Pro",
                'subtitle': "L'outil professionnel d'extraction de données marketing",
                'placeholder': "Collez l'URL de la catégorie Jumia (ex: https://www.jumia.sn/smartphones/)",
                'btn_analyze': "Analyser la catégorie",
                'btn_extract': "Lancer l'extraction",
                'lbl_pages_choice': "Sélectionnez le volume à extraire :",
                'analysis_found': "✅ Analyse réussie : Environ {} produits trouvés sur {} pages.",
                'processing': "Extraction en cours : Page {} sur {}...",
                'saving': "Génération du fichier Excel...",
                'success': "Succès ! {} produits ont été exportés avec succès.",
                'error': "Une erreur est survenue : {}",
                'open_folder': "Ouvrir le dossier de destination",
                'logs': "Journal des opérations",
                'log_analyzing': "Analyse de la structure : {} ...",
                'log_conn_error': "Erreur de connexion (Code : {})",
                'log_analysis_complete': "Structure identifiée. {} pages disponibles.",
                'log_no_data': "Aucun produit détecté sur cette page.",
                'popup_title': "Confirmation de l'extraction",
                'popup_msg': "Vous allez extraire les données de {} produits.\nTemps estimé : environ {} secondes.",
                'btn_cancel': "Annuler",
                'btn_confirm': "Confirmer et Démarrer",
            }
        else:
            return {
                'title': "Jumia Smart Scraper Pro",
                'subtitle': "Professional marketing data extraction tool",
                'placeholder': "Paste Jumia category URL (e.g., https://www.jumia.com/laptops/)",
                'btn_analyze': "Analyze Category",
                'btn_extract': "Start Extraction",
                'lbl_pages_choice': "Select extraction volume:",
                'analysis_found': "✅ Analysis successful: Approx {} items on {} pages.",
                'processing': "Extracting: Page {} of {}...",
                'saving': "Generating Excel file...",
                'success': "Success! {} products exported successfully.",
                'error': "An error occurred: {}",
                'open_folder': "Open destination folder",
                'logs': "Operation Log",
                'log_analyzing': "Analyzing structure: {} ...",
                'log_conn_error': "Connection error (Code: {})",
                'log_analysis_complete': "Structure identified. {} pages detected.",
                'log_no_data': "No products found on this page.",
                'popup_title': "Extraction Confirmation",
                'popup_msg': "You are about to extract {} products.\nEstimated time: approx {} seconds.",
                'btn_cancel': "Cancel",
                'btn_confirm': "Confirm & Start",
            }

    txt = get_texts()

    # --- 3. Composants UI avec Design Premium ---
    
    title_row = ft.Row(
        [
            ft.Icon(ft.icons.SHOPPING_CART_CHECKOUT_ROUNDED, color="orange", size=40),
            ft.Text(txt['title'], size=32, weight=ft.FontWeight.BOLD, color="orange")
        ],
        alignment=ft.MainAxisAlignment.CENTER
    )
    
    subtitle_text = ft.Text(txt['subtitle'], italic=True, color="grey", size=14)

    # Correction critique : Utilisation de hint_text
    url_input = ft.TextField(
        label="Lien Jumia",
        hint_text=txt['placeholder'],
        expand=True,
        border_color="orange",
        border_radius=15,
        prefix_icon=ft.icons.LINK,
        on_submit=lambda e: analyze_action(e)
    )
    
    btn_analyze = ft.ElevatedButton(
        text=txt['btn_analyze'],
        icon=ft.icons.SEARCH_ROUNDED,
        style=ft.ButtonStyle(
            color="white",
            bgcolor="orange",
            padding=20,
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
        on_click=lambda e: analyze_action(e)
    )

    lbl_analysis = ft.Container(
        content=ft.Text("", color="green_accent", weight=ft.FontWeight.W_600),
        padding=10,
        bgcolor=ft.colors.with_opacity(0.1, "green"),
        border_radius=10,
        visible=False
    )

    dropdown_pages = ft.Dropdown(
        width=120,
        border_radius=10,
        label="Pages",
        border_color="orange"
    )
    
    btn_extract = ft.ElevatedButton(
        text=txt['btn_extract'],
        icon=ft.icons.PLAY_ARROW_ROUNDED,
        style=ft.ButtonStyle(
            color="white",
            bgcolor="green",
            padding=20,
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
        disabled=True,
        on_click=lambda e: extract_action(e)
    )
    
    extraction_options_row = ft.Row(
        [
            ft.Text(txt['lbl_pages_choice'], weight=ft.FontWeight.BOLD),
            dropdown_pages,
            btn_extract
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        visible=False,
        spacing=20
    )

    progress_bar = ft.ProgressBar(visible=False, color="orange", height=10, border_radius=5)
    progress_status = ft.Text("", size=12, italic=True)

    log_column = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=5)
    log_container = ft.Container(
        content=log_column,
        border=ft.border.all(1, "grey700"),
        border_radius=10,
        padding=15,
        bgcolor="#1E1E1E",
        height=250,
        expand=True
    )
    
    btn_open_folder = ft.ElevatedButton(
        text=txt['open_folder'],
        icon=ft.icons.FOLDER_OPEN_ROUNDED,
        style=ft.ButtonStyle(color="orange"),
        visible=False
    )

    # --- Popups ---
    confirm_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(txt['popup_title']),
        content=ft.Text(""),
        actions=[
            ft.TextButton(txt['btn_cancel'], on_click=lambda e: close_dialog()),
            ft.ElevatedButton(txt['btn_confirm'], bgcolor="orange", color="white", on_click=lambda e: start_extraction_thread()),
        ],
    )

    def close_dialog():
        page.dialog.open = False
        btn_extract.disabled = False
        page.update()

    def add_log(message, color="white"):
        log_column.controls.append(
            ft.Row([
                ft.Text(f"[{datetime.now().strftime('%H:%M:%S')}]", color="grey", size=11),
                ft.Text(message, color=color, size=12, selectable=True)
            ])
        )
        page.update()
        log_column.scroll_to(offset=-1, duration=300)

    # --- Logique d'Analyse ---
    def analyze_action(e):
        url = url_input.value.strip()
        if not url or "jumia" not in url.lower():
            url_input.error_text = "Veuillez entrer une URL Jumia valide"
            page.update()
            return
        
        url_input.error_text = None
        btn_analyze.disabled = True
        progress_bar.visible = True
        log_column.controls.clear()
        page.update()
        threading.Thread(target=run_analysis, args=(url,), daemon=True).start()

    def run_analysis(url):
        try:
            add_log(txt['log_analyzing'].format(url), "cyan")
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            res = requests.get(url, headers=headers, timeout=15)
            
            if res.status_code != 200:
                add_log(txt['log_conn_error'].format(res.status_code), "red")
                return

            parsed = urlparse(url)
            analysis_result["base_url"] = f"{parsed.scheme}://{parsed.netloc}"
            soup = BeautifulSoup(res.content, 'html.parser')
            
            # Détection des pages
            last_page = 1
            pagination = soup.find_all('a', class_='pg')
            for pg in pagination:
                try:
                    num = re.sub(r'[^\d]', '', pg.text)
                    if num.isdigit():
                        val = int(num)
                        if val > last_page: last_page = val
                except: continue
            
            analysis_result["total_pages"] = last_page
            
            # Détection du nombre de produits
            count_tag = soup.find('p', class_="-gy5")
            prod_count_str = "0"
            if count_tag:
                prod_count_str = ''.join(filter(str.isdigit, count_tag.text))
            
            analysis_result["total_products"] = int(prod_count_str) if prod_count_str else 0
            
            update_ui_after_analysis(prod_count_str if prod_count_str else "N/A", last_page)
            add_log(txt['log_analysis_complete'].format(last_page), "green")
            
        except Exception as ex:
            add_log(txt['error'].format(str(ex)), "red")
        finally:
            progress_bar.visible = False
            btn_analyze.disabled = False
            page.update()

    def update_ui_after_analysis(count, pages):
        lbl_analysis.content.value = txt['analysis_found'].format(count, pages)
        lbl_analysis.visible = True
        
        # Options intelligentes de pagination
        opts = [1, 5, 10, 20, 50, pages]
        unique_opts = sorted(list(set([o for o in opts if o <= pages])))
        dropdown_pages.options = [ft.dropdown.Option(str(i)) for i in unique_opts]
        dropdown_pages.value = "1"
        
        extraction_options_row.visible = True
        btn_extract.disabled = False
        page.update()

    # --- Logique d'Extraction ---
    def extract_action(e):
        limit = int(dropdown_pages.value)
        est_items = limit * 40 # Jumia affiche ~40 produits par page
        confirm_dialog.content.value = txt['popup_msg'].format(est_items, int(limit * 1.5))
        page.dialog = confirm_dialog
        confirm_dialog.open = True
        page.update()

    def start_extraction_thread():
        confirm_dialog.open = False
        btn_extract.disabled = True
        url_input.disabled = True
        btn_analyze.disabled = True
        progress_bar.visible = True
        page.update()
        threading.Thread(target=run_extraction, args=(url_input.value, int(dropdown_pages.value)), daemon=True).start()

    def run_extraction(url, limit):
        data = []
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        base_path = url.split('?')[0]
        
        try:
            for p in range(1, limit + 1):
                p_url = f"{base_path}?page={p}" if '?' not in base_path else f"{base_path}&page={p}"
                progress_status.value = txt['processing'].format(p, limit)
                add_log(progress_status.value, "orange")
                
                res = requests.get(p_url, headers=headers, timeout=20)
                soup = BeautifulSoup(res.content, 'html.parser')
                items = soup.find_all('article', class_='prd')
                
                if not items:
                    add_log(f"Fin précoce à la page {p} (aucun produit)", "yellow")
                    break

                for it in items:
                    try:
                        name_tag = it.find('h3', class_='name')
                        price_tag = it.find('div', class_='prc')
                        link_tag = it.find('a', class_='core')
                        brand = it.get('data-brand', 'N/A')
                        
                        full_link = ""
                        if link_tag:
                            href = link_tag.get('href', '')
                            full_link = analysis_result["base_url"] + href if href.startswith('/') else href

                        data.append({
                            "Date": datetime.now().strftime("%d/%m/%Y"),
                            "ID": it.get('data-ga4-item_id', 'N/A'),
                            "Marque": brand,
                            "Désignation": name_tag.text.strip() if name_tag else "N/A",
                            "Prix": re.sub(r'[^\d]', '', price_tag.text) if price_tag else "0",
                            "Lien": full_link
                        })
                    except: continue
                
                time.sleep(0.5) # Politesse serveur

            if data:
                add_log(txt['saving'], "cyan")
                df = pd.DataFrame(data)
                filename = f"Jumia_Data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                save_path = os.path.join(os.path.expanduser('~'), 'Documents', filename)
                
                df.to_excel(save_path, index=False)
                add_log(txt['success'].format(len(data)), "green")
                
                btn_open_folder.visible = True
                btn_open_folder.on_click = lambda _: os.startfile(os.path.dirname(save_path))
            else:
                add_log(txt['log_no_data'], "red")
                
        except Exception as ex:
            add_log(txt['error'].format(str(ex)), "red")
        finally:
            progress_bar.visible = False
            progress_status.value = ""
            url_input.disabled = False
            btn_analyze.disabled = False
            btn_extract.disabled = False
            page.update()

    # --- Mise en page finale (Responsive) ---
    main_layout = ft.Container(
        content=ft.Column([
            title_row,
            ft.Row([subtitle_text], alignment=ft.MainAxisAlignment.CENTER),
            ft.Divider(height=20, color="transparent"),
            ft.Row([url_input, btn_analyze], spacing=10),
            lbl_analysis,
            ft.Divider(height=10, color="transparent"),
            extraction_options_row,
            progress_bar,
            progress_status,
            ft.Text(txt['logs'], weight=ft.FontWeight.BOLD, size=16),
            log_container,
            ft.Row([btn_open_folder], alignment=ft.MainAxisAlignment.CENTER)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        padding=10,
        expand=True
    )

    page.add(main_layout)

if __name__ == "__main__":
    # Correction pour les environnements packagés Windows
    ft.app(target=main)
