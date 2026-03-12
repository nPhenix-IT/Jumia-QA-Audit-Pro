import flet as ft
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import sys
import threading
from datetime import datetime
import time
from urllib.parse import urlparse
import subprocess
import re

def main(page: ft.Page):
    # --- 1. Configuration de la page ---
    page.title = "Jumia QA Audit Pro"
    page.theme_mode = ft.ThemeMode.DARK 
    page.window_width = 950 
    page.window_height = 950
    page.padding = 20
    page.window_icon = "https://www.jumia.sn/assets_he/favicon.adbd556a.svg"
    
    # --- Variables d'État ---
    state = {
        "file_path": None,
        "is_running": False,
        "is_paused": False,
        "stop_requested": False,
        "found_products": [],
        "start_time": None,
        "estimated_total_seconds": 0
    }

    # --- 2. Logique de traitement de fichier ---
    def process_selected_file(path, name=None):
        if not path: return
        path = path.strip().replace('"', '').replace("'", "")
        
        if os.path.exists(path) and path.lower().endswith(('.xlsx', '.xls')):
            state["file_path"] = path
            file_name = name if name else os.path.basename(path)
            lbl_file_selected.value = f"✅ Fichier prêt : {file_name}"
            lbl_file_selected.color = "green"
            path_input.value = path
            drop_zone.border_color = "green"
            btn_start_audit.disabled = False
            add_log(f"Fichier validé : {file_name}", "green")
        else:
            add_log("Erreur : Fichier invalide ou introuvable. Utilisez un .xlsx ou .xls", "red")
            lbl_file_selected.value = "Format de fichier non supporté"
            lbl_file_selected.color = "red"
        page.update()

    def on_file_result(e: ft.FilePickerResultEvent):
        if e.files:
            process_selected_file(e.files[0].path, e.files[0].name)

    file_picker = ft.FilePicker(on_result=on_file_result)
    page.overlay.append(file_picker)

    # --- 3. Modales & Dialogues ---
    def close_dlg(e):
        confirm_dialog.open = False
        page.update()

    def confirm_start(e):
        confirm_dialog.open = False
        page.update()
        start_audit_process()

    confirm_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Confirmation de l'Audit"),
        content=ft.Text("Calcul en cours..."),
        actions=[
            ft.TextButton("Oui, démarrer", on_click=confirm_start),
            ft.TextButton("Non, annuler", on_click=close_dlg),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(confirm_dialog)

    # --- 4. Composants de l'Interface ---
    # Titre avec Icône
    title_row = ft.Row(
        [
            ft.Image(src="https://www.jumia.sn/assets_he/favicon.adbd556a.svg", width=40, height=40),
            ft.Text("Jumia QA Audit Pro", size=30, weight=ft.FontWeight.BOLD, color="blue"),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
    )
    
    subtitle_text = ft.Text("Audit de la qualité du catalogue (Images, Descriptions, Miniatures)", size=14, color="grey")
    
    lbl_file_selected = ft.Text("Glissez votre fichier Excel ici", color="orange", size=16, weight="bold")

    path_input = ft.TextField(
        label="Ou collez le chemin du fichier ici",
        hint_text="C:/Users/Nom/Documents/boutiques.xlsx",
        text_size=12,
        on_change=lambda e: process_selected_file(e.control.value),
        suffix_icon=ft.Icons.CHECK_CIRCLE_OUTLINE
    )

    drop_zone = ft.Container(
        content=ft.Column([
            ft.Icon(ft.Icons.UPLOAD_FILE_ROUNDED, size=50, color="blue"),
            lbl_file_selected,
            ft.Text("ou cliquez pour parcourir", size=12, color="grey")
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        margin=10,
        padding=30,
        alignment=ft.alignment.center,
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
        border=ft.border.all(2, ft.Colors.BLUE_400),
        border_radius=15,
        width=500,
        height=200,
        on_click=lambda _: file_picker.pick_files(allowed_extensions=["xlsx", "xls"]),
    )

    btn_start_audit = ft.ElevatedButton(
        text="Analyser le fichier et démarrer",
        icon=ft.Icons.PLAY_ARROW,
        style=ft.ButtonStyle(padding=20, shape=ft.RoundedRectangleBorder(radius=10)),
        bgcolor="blue", color="white",
        disabled=True,
        on_click=lambda e: prepare_audit()
    )

    # Boutons de contrôle (Pause / Stop)
    def toggle_pause(e):
        state["is_paused"] = not state["is_paused"]
        btn_pause.icon = ft.Icons.PLAY_ARROW if state["is_paused"] else ft.Icons.PAUSE
        btn_pause.text = "Reprendre" if state["is_paused"] else "Pause"
        btn_pause.bgcolor = "green" if state["is_paused"] else "orange"
        add_log("Audit mis en pause" if state["is_paused"] else "Reprise de l'audit", "orange")
        page.update()

    def request_stop(e):
        state["stop_requested"] = True
        btn_stop.disabled = True
        btn_pause.disabled = True
        add_log("Arrêt demandé... finalisation du lot actuel", "red")
        page.update()

    btn_pause = ft.ElevatedButton(
        "Pause", icon=ft.Icons.PAUSE, bgcolor="orange", color="white", 
        visible=False, on_click=toggle_pause
    )
    btn_stop = ft.ElevatedButton(
        "Arrêter", icon=ft.Icons.STOP, bgcolor="red", color="white", 
        visible=False, on_click=request_stop
    )

    controls_row = ft.Row(
        [btn_pause, btn_stop],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=20,
        visible=False
    )

    progress_bar = ft.ProgressBar(visible=False, color="orange", width=500)
    progress_text = ft.Text("", visible=False, color="cyan")
    
    elapsed_time_text = ft.Text("Temps écoulé : 00:00", size=12, color="grey", visible=False)
    remaining_time_text = ft.Text("Temps restant : --:--", size=12, color="orange", visible=False)
    
    time_row = ft.Row(
        [elapsed_time_text, remaining_time_text],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        width=500,
        visible=False
    )

    log_column = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=5)
    log_container = ft.Container(
        content=log_column,
        border=ft.border.all(1, "outline"), 
        border_radius=10,
        padding=15,
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLACK), 
        height=250, 
    )

    btn_open_folder = ft.ElevatedButton("Ouvrir le dossier des résultats", icon=ft.Icons.FOLDER_OPEN, visible=False)

    # --- 5. Logique d'Audit ---
    def add_log(message, color="white"):
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_column.controls.append(ft.Text(f"[{timestamp}] {message}", color=color, font_family="Consolas", size=12))
        page.update()
        log_column.scroll_to(offset=-1, duration=100)

    def format_time(seconds):
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"

    def reset_form():
        state["file_path"] = None
        state["found_products"] = []
        state["is_running"] = False
        state["is_paused"] = False
        state["stop_requested"] = False
        
        path_input.value = ""
        path_input.disabled = False
        lbl_file_selected.value = "Glissez votre fichier Excel ici"
        lbl_file_selected.color = "orange"
        drop_zone.border_color = ft.Colors.BLUE_400
        drop_zone.disabled = False
        btn_start_audit.disabled = True
        progress_bar.visible = False
        progress_text.visible = False
        time_row.visible = False
        elapsed_time_text.visible = False
        remaining_time_text.visible = False
        
        # Reset boutons contrôle
        controls_row.visible = False
        btn_pause.visible = False
        btn_pause.text = "Pause"
        btn_pause.icon = ft.Icons.PAUSE
        btn_pause.bgcolor = "orange"
        btn_stop.visible = False
        btn_stop.disabled = False
        btn_pause.disabled = False
        
        page.update()

    def prepare_audit():
        if not state["file_path"] or state["is_running"]: return
        
        btn_start_audit.disabled = True
        progress_bar.visible = True
        progress_text.value = "Analyse préliminaire des boutiques..."
        progress_text.visible = True
        page.update()
        
        threading.Thread(target=analyze_links_before_start, daemon=True).start()

    def analyze_links_before_start():
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        try:
            df = pd.read_excel(state["file_path"])
            store_urls = df.iloc[:, 0].dropna().tolist()
            
            all_prods = []
            for url in store_urls:
                all_prods.extend(get_product_links(url, headers))
            
            state["found_products"] = all_prods
            count = len(all_prods)
            
            state["estimated_total_seconds"] = int(count * 1.7) + 5
            time_str = format_time(state["estimated_total_seconds"])

            confirm_dialog.content = ft.Text(
                f"L'analyse a trouvé {count} articles à auditer.\n\n"
                f"Temps estimé : environ {time_str}.\n\n"
                "Voulez-vous lancer le traitement ?"
            )
            confirm_dialog.open = True
            
        except Exception as e:
            add_log(f"Erreur d'analyse : {e}", "red")
        finally:
            progress_bar.visible = False
            progress_text.visible = False
            btn_start_audit.disabled = False
            page.update()

    def start_audit_process():
        state["is_running"] = True
        state["is_paused"] = False
        state["stop_requested"] = False
        state["start_time"] = time.time()
        
        btn_start_audit.disabled = True
        path_input.disabled = True
        drop_zone.disabled = True
        
        progress_bar.visible = True
        progress_text.visible = True
        time_row.visible = True
        elapsed_time_text.visible = True
        remaining_time_text.visible = True
        
        # Afficher boutons de contrôle
        controls_row.visible = True
        btn_pause.visible = True
        btn_stop.visible = True
        
        btn_open_folder.visible = False
        log_column.controls.clear()
        page.update()
        threading.Thread(target=run_audit, daemon=True).start()

    def get_product_links(store_url, headers):
        product_links = []
        current_url = store_url
        parsed_uri = urlparse(store_url)
        base_domain = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
        while current_url:
            try:
                response = requests.get(current_url, headers=headers, timeout=15)
                if response.status_code != 200: break
                soup = BeautifulSoup(response.content, 'html.parser')
                articles = soup.find_all('article', class_='prd')
                for item in articles:
                    core_link = item.find('a', class_='core')
                    if core_link and 'href' in core_link.attrs:
                        href = core_link['href']
                        link = f"{base_domain}{href}" if href.startswith('/') else href
                        name = item.find('h3', class_='name').get_text(strip=True) if item.find('h3', class_='name') else "N/A"
                        product_links.append({"url": link, "name": name, "store_url": store_url})
                
                next_btn = soup.find('a', attrs={'aria-label': 'Page suivante'}) or soup.find('a', attrs={'aria-label': 'Next Page'})
                if next_btn and 'href' in next_btn.attrs:
                    next_href = next_btn['href']
                    current_url = f"{base_domain}{next_href}" if next_href.startswith('/') else next_href
                else: break
            except: break
        return product_links

    def run_audit():
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        results = {"desc": [], "bullets": [], "gallery": []}
        products = state["found_products"]
        total = len(products)
        processed_count = 0
        
        try:
            add_log(f"Démarrage de l'audit pour {total} articles...", "cyan")

            for p_idx, prod in enumerate(products, 1):
                # 1. Gérer l'Arrêt
                if state["stop_requested"]:
                    add_log("Audit arrêté prématurément par l'utilisateur.", "red")
                    break
                
                # 2. Gérer la Pause
                while state["is_paused"]:
                    time.sleep(1)
                    if state["stop_requested"]: break
                if state["stop_requested"]: break

                # Mise à jour des compteurs de temps
                current_time = time.time()
                elapsed = current_time - state["start_time"]
                elapsed_time_text.value = f"Temps écoulé : {format_time(elapsed)}"
                
                if p_idx > 1:
                    avg_time_per_item = elapsed / p_idx
                    remaining_items = total - p_idx
                    remaining_sec = avg_time_per_item * remaining_items
                    remaining_time_text.value = f"Temps restant : ~{format_time(remaining_sec)}"
                
                progress_text.value = f"Traitement article {p_idx}/{total}"
                progress_bar.value = p_idx / total
                page.update()
                
                try:
                    time.sleep(0.5) 
                    res = requests.get(prod["url"], headers=headers, timeout=10)
                    if res.status_code != 200: continue
                    soup = BeautifulSoup(res.content, 'html.parser')
                    
                    # Extraction SKU
                    sku_val = "N/A"
                    sku_ul = soup.find('ul', class_='-pvs -mvxs -phm -lsn')
                    if sku_ul:
                        sku_li = sku_ul.find('li', class_='-pvxs')
                        if sku_li and "SKU" in sku_li.get_text():
                            sku_val = sku_li.get_text(strip=True).replace("SKU:", "").strip()
                    
                    # Extraction Vendeur
                    seller_val = "N/A"
                    seller_p = soup.find('p', class_='-m -pbs')
                    if seller_p:
                        seller_val = seller_p.get_text(strip=True)

                    base_info = {
                        "SKU": sku_val, 
                        "Nom": prod["name"], 
                        "Vendeur": seller_val,
                        "Lien": prod["url"], 
                        "Boutique": prod["store_url"]
                    }
                    
                    # Audit Logique
                    desc_div = soup.find('div', class_=lambda c: c and 'card' in c and 'aim' in c and '-mtm' in c)
                    if not desc_div or not desc_div.find('img'): results["desc"].append(base_info)
                    
                    short_desc_div = soup.find('div', class_=lambda c: c and 'card-b' in c and '-fh' in c)
                    if not short_desc_div or not short_desc_div.find('li'): results["bullets"].append(base_info)
                    
                    gallery_div = soup.find('div', class_=lambda c: c and '-ptxs' in c and '-pbs' in c)
                    if gallery_div:
                        if len(gallery_div.find_all('img')) == 1: results["gallery"].append(base_info)
                    else: results["gallery"].append(base_info)
                    
                    processed_count = p_idx
                except: continue

            # Exportation des résultats même en cas d'arrêt partiel
            if processed_count > 0:
                docs_path = os.path.join(os.path.expanduser('~'), 'Documents')
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                mapping = {"desc": "Sans_Images_Description", "bullets": "Sans_Bullet_Points", "gallery": "Image_Galerie_Unique"}
                
                generated = False
                for key, name in mapping.items():
                    if results[key]:
                        path = os.path.join(docs_path, f"Audit_{name}_{ts}.xlsx")
                        pd.DataFrame(results[key]).to_excel(path, index=False)
                        add_log(f"Rapport généré : {name}", "green")
                        generated = True
                
                if not generated:
                    add_log("Audit terminé : Aucun défaut détecté !", "green")
                else:
                    add_log("✅ Rapports enregistrés dans Documents", "green")
                
                btn_open_folder.visible = True
                btn_open_folder.on_click = lambda _: (os.startfile(docs_path) if sys.platform == 'win32' else subprocess.run(['open', docs_path]))
            
            remaining_time_text.value = "Statut : Terminé" if not state["stop_requested"] else "Statut : Interrompu"
            
            time.sleep(3)
            add_log("Réinitialisation du formulaire...", "grey")
            reset_form()

        except Exception as e: 
            add_log(f"Erreur fatale : {e}", "red")
            reset_form()
        finally:
            page.update()

    # --- 6. Assemblage ---
    page.add(
        ft.Column([
            title_row,
            ft.Row([subtitle_text], alignment=ft.MainAxisAlignment.CENTER),
            ft.Divider(height=10, color="transparent"),
            ft.Column([
                drop_zone,
                ft.Container(path_input, width=500),
                ft.Divider(height=5, color="transparent"),
                btn_start_audit,
                progress_text,
                progress_bar,
                time_row,
                controls_row, 
                ft.Divider(height=10, color="transparent"),
                ft.Text("Journal d'audit :", weight="bold"),
                log_container,
                btn_open_folder
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    )
    page.update()

if __name__ == "__main__":
    ft.app(target=main)