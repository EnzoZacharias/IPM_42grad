from mistralai import Mistral
import os

# Rollen-Definitionen mit System-Prompts
ROLES = {
    "it-experte": {
        "name": "IT-Experte",
        "system_prompt": "Du bist ein erfahrener IT-Experte mit tiefem technischem Wissen. Du gibst präzise technische Antworten, erklärst Konzepte detailliert und hilfst bei technischen Problemen. Du verwendest Fachbegriffe, wenn nötig, und gibst praktische Lösungsvorschläge."
    },
    "management": {
        "name": "Management-Berater",
        "system_prompt": "Du bist ein strategischer Management-Berater. Du denkst in geschäftlichen Zusammenhängen, fokussierst dich auf ROI, Effizienz und Unternehmenszielen. Du gibst Ratschläge zu Organisation, Führung und strategischen Entscheidungen in einer professionellen Business-Sprache."
    },
    "facharbeiter": {
        "name": "Facharbeiter",
        "system_prompt": "Du bist ein erfahrener Facharbeiter mit praktischem Know-how. Du gibst bodenständige, praxisnahe Antworten und konzentrierst dich auf die Umsetzung und Durchführung von Aufgaben. Du sprichst verständlich und direkt über praktische Arbeitsabläufe."
    }
}

class InteractiveMistralChat:
    def __init__(self, api_key):
        self.client = Mistral(api_key=api_key)
        self.model = "mistral-small-latest"
        self.messages = []
        self.current_role = "it-experte"
        self.set_system_prompt()
    
    def set_system_prompt(self):
        """Setzt den System-Prompt basierend auf der aktuellen Rolle"""
        system_message = {
            "role": "system",
            "content": ROLES[self.current_role]["system_prompt"]
        }
        # Entferne alte System-Messages und füge neue hinzu
        self.messages = [msg for msg in self.messages if msg["role"] != "system"]
        self.messages.insert(0, system_message)
    
    def change_role(self, role_key):
        """Wechselt die Rolle des Assistenten"""
        if role_key in ROLES:
            self.current_role = role_key
            self.set_system_prompt()
            print(f"\n✓ Rolle gewechselt zu: {ROLES[role_key]['name']}\n")
        else:
            print(f"\n✗ Unbekannte Rolle. Verfügbare Rollen: {', '.join(ROLES.keys())}\n")
    
    def clear_chat(self):
        """Löscht die Chat-Historie"""
        self.messages = []
        self.set_system_prompt()
        print("\n✓ Chat-Verlauf gelöscht\n")
    
    def show_history(self):
        """Zeigt die Chat-Historie an"""
        print("\n" + "="*80)
        print("CHAT-VERLAUF:")
        print("="*80)
        for msg in self.messages:
            if msg["role"] == "system":
                print(f"\n[SYSTEM] {msg['content'][:100]}...")
            elif msg["role"] == "user":
                print(f"\n[DU] {msg['content']}")
            elif msg["role"] == "assistant":
                print(f"\n[ASSISTENT] {msg['content']}")
        print("="*80 + "\n")
    
    def show_help(self):
        """Zeigt verfügbare Befehle an"""
        print("\n" + "="*80)
        print("VERFÜGBARE BEFEHLE:")
        print("="*80)
        print("/help          - Zeigt diese Hilfe an")
        print("/clear         - Löscht den Chat-Verlauf")
        print("/history       - Zeigt den kompletten Chat-Verlauf")
        print("/role          - Zeigt die aktuelle Rolle")
        print("/role <name>   - Wechselt die Rolle (it-experte, management, facharbeiter)")
        print("/quit oder /exit - Beendet den Chat")
        print("="*80 + "\n")
    
    def show_current_role(self):
        """Zeigt die aktuelle Rolle an"""
        print(f"\n✓ Aktuelle Rolle: {ROLES[self.current_role]['name']}\n")
    
    def handle_command(self, command):
        """Verarbeitet Befehle, die mit / beginnen"""
        parts = command.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        
        if cmd == "/help":
            self.show_help()
            return True
        elif cmd == "/clear":
            self.clear_chat()
            return True
        elif cmd == "/history":
            self.show_history()
            return True
        elif cmd == "/role":
            if len(parts) > 1:
                self.change_role(parts[1].lower())
            else:
                self.show_current_role()
            return True
        elif cmd in ["/quit", "/exit"]:
            print("\n👋 Auf Wiedersehen!\n")
            return False
        else:
            print(f"\n✗ Unbekannter Befehl: {cmd}")
            print("Tippe /help für eine Liste verfügbarer Befehle\n")
            return True
    
    def send_message(self, user_message):
        """Sendet eine Nachricht an die API und streamt die Antwort"""
        self.messages.append({
            "role": "user",
            "content": user_message
        })
        
        try:
            response = self.client.chat.stream(
                model=self.model,
                messages=self.messages
            )
            
            assistant_message = ""
            for chunk in response:
                if chunk.data.choices[0].delta.content:
                    content = chunk.data.choices[0].delta.content
                    print(content, end="", flush=True)
                    assistant_message += content
            
            self.messages.append({
                "role": "assistant",
                "content": assistant_message
            })
            
            return assistant_message
        except Exception as e:
            print(f"\n✗ Fehler bei der API-Anfrage: {e}\n")
            # Entferne die letzte User-Message bei Fehler
            self.messages.pop()
            return None
    
    def run(self):
        """Startet den interaktiven Chat"""
        print("\n" + "="*80)
        print("MISTRAL INTERAKTIVER CHAT")
        print("="*80)
        print(f"Aktuelle Rolle: {ROLES[self.current_role]['name']}")
        print("Tippe /help für verfügbare Befehle")
        print("="*80 + "\n")
        
        while True:
            try:
                user_input = input("Du: ").strip()
                
                if not user_input:
                    continue
                
                # Prüfe auf Befehle
                if user_input.startswith("/"):
                    should_continue = self.handle_command(user_input)
                    if not should_continue:
                        break
                    continue
                
                # Normale Nachricht senden
                print("\nAssistent: ", end="", flush=True)
                response = self.send_message(user_input)
                if response:
                    print(response + "\n")
                
            except KeyboardInterrupt:
                print("\n\n👋 Chat mit Ctrl+C beendet. Auf Wiedersehen!\n")
                break
            except EOFError:
                print("\n\n👋 Auf Wiedersehen!\n")
                break


def main():
    api_key = os.environ.get("MISTRAL_API_KEY")
    
    if not api_key:
        print("✗ Fehler: MISTRAL_API_KEY Umgebungsvariable nicht gesetzt!")
        return
    
    chat = InteractiveMistralChat(api_key)
    chat.run()


if __name__ == "__main__":
    main()