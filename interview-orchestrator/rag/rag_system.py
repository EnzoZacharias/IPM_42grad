"""
RAG System für das Interview-Tool
Verarbeitet PDF- und TXT-Dateien und ermöglicht semantische Suche
"""
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

# PDF und Text-Verarbeitung
try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

# LangChain für Dokumentenverarbeitung und Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document


logger = logging.getLogger(__name__)


class RAGSystem:
    """
    RAG-System zum Verarbeiten und Abfragen von hochgeladenen Dokumenten.
    
    Features:
    - Lädt PDF und TXT-Dateien
    - Erstellt Embeddings mit sentence-transformers
    - Speichert Vektoren in FAISS
    - Ermöglicht semantische Suche
    """
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        top_k: int = 3
    ):
        """
        Initialisiert das RAG-System.
        
        Args:
            chunk_size: Größe der Text-Chunks in Zeichen
            chunk_overlap: Überlappung zwischen Chunks
            embedding_model: HuggingFace Embedding-Modell
            top_k: Anzahl der relevantesten Dokumente beim Retrieval
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.top_k = top_k
        
        # Text-Splitter für Chunking
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        
        # Embedding-Modell (läuft lokal)
        logger.info(f"Initialisiere Embedding-Modell: {embedding_model}")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        # Vector Store (wird bei initialize() erstellt)
        self.vectorstore: Optional[FAISS] = None
        self.documents: List[Document] = []
        self.is_initialized = False
    
    def load_documents(self, file_paths: List[str]) -> List[Document]:
        """
        Lädt Dokumente aus PDF- und TXT-Dateien.
        
        Args:
            file_paths: Liste von Dateipfaden
            
        Returns:
            Liste von LangChain Document-Objekten
        """
        documents = []
        
        logger.info(f"📂 Starte Laden von {len(file_paths)} Dateien...")
        
        for file_path in file_paths:
            path = Path(file_path)
            
            if not path.exists():
                logger.warning(f"⚠️  Datei nicht gefunden: {file_path}")
                continue
            
            try:
                logger.info(f"📄 Lade Datei: {path.name} ({path.suffix})")
                
                if path.suffix.lower() == '.pdf':
                    docs = self._load_pdf(file_path)
                    documents.extend(docs)
                    logger.info(f"  ✅ PDF geladen: {len(docs)} Seiten extrahiert")
                elif path.suffix.lower() in ['.txt', '.text']:
                    docs = self._load_txt(file_path)
                    documents.extend(docs)
                    logger.info(f"  ✅ TXT geladen: {len(docs)} Dokument(e)")
                else:
                    logger.warning(f"  ⚠️  Nicht unterstütztes Dateiformat: {path.suffix}")
                    
            except Exception as e:
                logger.error(f"  ❌ Fehler beim Laden von {path.name}: {str(e)}")
        
        logger.info(f"📊 Gesamt geladen: {len(documents)} Dokumente aus {len(file_paths)} Dateien")
        return documents
    
    def _load_pdf(self, file_path: str) -> List[Document]:
        """Lädt Text aus einer PDF-Datei."""
        if PdfReader is None:
            raise ImportError("PyPDF2 ist nicht installiert. Bitte installieren: pip install pypdf2")
        
        logger.debug(f"  📖 Extrahiere Text aus PDF: {file_path}")
        documents = []
        reader = PdfReader(file_path)
        
        total_pages = len(reader.pages)
        logger.debug(f"  📄 PDF hat {total_pages} Seiten")
        
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if text.strip():
                doc = Document(
                    page_content=text,
                    metadata={
                        'source': os.path.basename(file_path),
                        'page': page_num + 1,
                        'file_path': file_path
                    }
                )
                documents.append(doc)
                logger.debug(f"    Seite {page_num + 1}: {len(text)} Zeichen extrahiert")
            else:
                logger.debug(f"    Seite {page_num + 1}: Leer, übersprungen")
        
        logger.debug(f"  ✅ {len(documents)} von {total_pages} Seiten mit Inhalt")
        return documents
    
    def _load_txt(self, file_path: str) -> List[Document]:
        """Lädt Text aus einer TXT-Datei."""
        logger.debug(f"  📝 Lese TXT-Datei: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        logger.debug(f"  📊 TXT-Datei: {len(text)} Zeichen gelesen")
        
        if text.strip():
            doc = Document(
                page_content=text,
                metadata={
                    'source': os.path.basename(file_path),
                    'file_path': file_path
                }
            )
            logger.debug(f"  ✅ TXT-Dokument erstellt")
            return [doc]
        
        logger.debug(f"  ⚠️  TXT-Datei ist leer")
        return []
    
    def initialize(self, file_paths: List[str]) -> bool:
        """
        Initialisiert das RAG-System mit den gegebenen Dateien.
        Erstellt Embeddings und Vector Store.
        
        Args:
            file_paths: Liste von Dateipfaden
            
        Returns:
            True wenn erfolgreich, False sonst
        """
        if not file_paths:
            logger.warning("⚠️  Keine Dateien zum Initialisieren vorhanden")
            self.is_initialized = False
            return False
        
        try:
            logger.info(f"🔄 Initialisiere RAG-System mit {len(file_paths)} Dateien...")
            logger.info(f"📋 Dateien: {[os.path.basename(f) for f in file_paths]}")
            
            # Lade Dokumente
            self.documents = self.load_documents(file_paths)
            
            if not self.documents:
                logger.warning("⚠️  Keine Dokumente geladen")
                self.is_initialized = False
                return False
            
            logger.info(f"📄 {len(self.documents)} Dokumente geladen")
            
            # Splitte Dokumente in Chunks
            logger.info(f"✂️  Splitte Dokumente in Chunks (Größe: {self.chunk_size}, Überlappung: {self.chunk_overlap})...")
            chunks = self.text_splitter.split_documents(self.documents)
            logger.info(f"📊 {len(chunks)} Text-Chunks erstellt")
            
            # Zeige ersten Chunk als Beispiel (nur für Debugging)
            if chunks:
                first_chunk_preview = chunks[0].page_content[:200]
                logger.debug(f"🔍 Beispiel-Chunk: '{first_chunk_preview}...'")
            
            # Erstelle Vector Store mit Embeddings
            logger.info("🔮 Erstelle Embeddings und Vector Store...")
            logger.info("   ⏳ Dies kann einige Sekunden dauern...")
            self.vectorstore = FAISS.from_documents(chunks, self.embeddings)
            
            self.is_initialized = True
            logger.info("✅ RAG-System erfolgreich initialisiert")
            logger.info(f"📈 Statistiken: {self.get_stats()}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Fehler bei RAG-Initialisierung: {str(e)}", exc_info=True)
            self.is_initialized = False
            return False
    
    def retrieve_context(self, query: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Sucht relevante Dokumente für eine Anfrage.
        
        Args:
            query: Suchanfrage
            top_k: Anzahl der zurückzugebenden Dokumente (optional)
            
        Returns:
            Liste von Dokumenten mit Inhalt und Metadaten
        """
        if not self.is_initialized or self.vectorstore is None:
            logger.warning("⚠️  RAG-System ist nicht initialisiert")
            return []
        
        k = top_k or self.top_k
        
        try:
            logger.debug(f"🔍 Suche nach: '{query[:100]}...'")
            logger.debug(f"   Top-K: {k}")
            
            # Semantische Suche im Vector Store
            results = self.vectorstore.similarity_search_with_score(query, k=k)
            
            logger.debug(f"📊 {len(results)} Ergebnisse gefunden")
            
            # Formatiere Ergebnisse und filtere nach Relevanz-Threshold
            context_docs = []
            RELEVANCE_THRESHOLD = 0.5  # Nur Dokumente mit Similarity >= 50% verwenden
            
            for idx, (doc, score) in enumerate(results, 1):
                similarity = float(1 / (1 + score))
                
                # Filtere irrelevante Dokumente
                if similarity < RELEVANCE_THRESHOLD:
                    logger.debug(f"  {idx}. ⚠️  Übersprungen (Score: {similarity:.3f} < {RELEVANCE_THRESHOLD})")
                    continue
                
                context_docs.append({
                    'content': doc.page_content,
                    'metadata': doc.metadata,
                    'relevance_score': similarity
                })
                
                source = doc.metadata.get('source', 'Unbekannt')
                page = doc.metadata.get('page', '-')
                preview = doc.page_content[:100].replace('\n', ' ')
                logger.debug(f"  {idx}. ✅ Quelle: {source} | Seite: {page} | Score: {similarity:.3f}")
                logger.debug(f"     Preview: '{preview}...'")
            
            if context_docs:
                logger.info(f"✅ {len(context_docs)} relevante Dokumente gefunden (von {len(results)} geprüft)")
            else:
                logger.info(f"ℹ️  Keine relevanten Dokumente gefunden (alle unter Threshold {RELEVANCE_THRESHOLD})")
            
            return context_docs
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Retrieval: {str(e)}", exc_info=True)
            return []
    
    def get_context_for_question(self, question: str, max_context_length: int = 2000) -> str:
        """
        Holt relevanten Kontext für eine Interview-Frage.
        
        Args:
            question: Die Frage, für die Kontext gesucht wird
            max_context_length: Maximale Länge des Kontexts in Zeichen
            
        Returns:
            Formatierter Kontext-String (leer wenn keine relevanten Dokumente gefunden)
        """
        if not self.is_initialized:
            logger.debug("⚠️  RAG nicht initialisiert, kein Kontext verfügbar")
            return ""
        
        logger.info(f"🔍 Hole Kontext für Frage: '{question[:80]}...'")
        
        # Suche relevante Dokumente (bereits gefiltert nach Relevanz)
        docs = self.retrieve_context(question)
        
        if not docs:
            logger.info("ℹ️  Keine relevanten Dokumente gefunden - Kontext wird NICHT hinzugefügt")
            return ""
        
        # Formatiere Kontext
        context_parts = []
        current_length = 0
        
        logger.debug(f"📝 Formatiere Kontext (max {max_context_length} Zeichen)...")
        
        for i, doc in enumerate(docs, 1):
            source = doc['metadata'].get('source', 'Unbekannt')
            page = doc['metadata'].get('page')
            content = doc['content'].strip()
            score = doc.get('relevance_score', 0)
            
            # Erstelle Kontext-Header mit Score
            if page:
                header = f"[Quelle: {source}, Seite {page}, Relevanz: {score:.0%}]"
            else:
                header = f"[Quelle: {source}, Relevanz: {score:.0%}]"
            
            # Prüfe Längenlimit
            part = f"{header}\n{content}\n"
            if current_length + len(part) > max_context_length:
                logger.debug(f"  ⚠️  Längenlimit erreicht, stoppe bei Dokument {i-1}")
                break
            
            context_parts.append(part)
            current_length += len(part)
            logger.debug(f"  ✅ Dokument {i} hinzugefügt ({len(part)} Zeichen, Score: {score:.0%})")
        
        if context_parts:
            context = "\n---\n".join(context_parts)
            final_context = f"RELEVANTER KONTEXT AUS DOKUMENTEN:\n\n{context}\n"
            logger.info(f"✅ Kontext erstellt: {len(final_context)} Zeichen aus {len(context_parts)} Dokumenten")
            return final_context
        
        logger.info("ℹ️  Kein Kontext erstellt (keine relevanten Dokumente)")
        return ""
    
    def generate_document_summary(self, llm_client, max_summary_length: int = 1500) -> str:
        """
        Generiert eine Zusammenfassung aller geladenen Dokumente via LLM.
        
        Args:
            llm_client: Der Mistral LLM Client für die Zusammenfassung
            max_summary_length: Maximale Länge der Zusammenfassung in Zeichen
            
        Returns:
            Zusammenfassung der Dokumente (leer wenn keine Dokumente vorhanden)
        """
        if not self.is_initialized or not self.documents:
            logger.info("ℹ️  Keine Dokumente für Zusammenfassung vorhanden")
            return ""
        
        logger.info("📝 Generiere Dokument-Zusammenfassung via LLM...")
        
        # Sammle alle Dokument-Inhalte
        all_content = []
        for doc in self.documents:
            source = doc.metadata.get('source', 'Unbekannt')
            content = doc.page_content.strip()
            all_content.append(f"[Aus: {source}]\n{content}")
        
        combined_text = "\n\n---\n\n".join(all_content)
        
        # Kürze wenn zu lang (LLM hat Token-Limits)
        MAX_INPUT_LENGTH = 10000
        if len(combined_text) > MAX_INPUT_LENGTH:
            logger.debug(f"⚠️  Dokumente zu lang ({len(combined_text)} Zeichen), kürze auf {MAX_INPUT_LENGTH}...")
            combined_text = combined_text[:MAX_INPUT_LENGTH] + "\n\n[... Weitere Inhalte gekürzt ...]"
        
        # Prompt für Zusammenfassung
        prompt = f"""Analysiere die folgenden Unternehmensdokumente und erstelle eine prägnante Zusammenfassung.

DOKUMENTE:
{combined_text}

AUFGABE:
Erstelle eine strukturierte Zusammenfassung mit folgenden Punkten:
- Welches Unternehmen/Organisation wird beschrieben?
- Hauptaktivitäten und Geschäftsbereich
- Organisationsstruktur und Rollen
- Wichtige Prozesse oder Systeme
- Besonderheiten oder Herausforderungen

Halte die Zusammenfassung prägnant (max. 800 Wörter) und fokussiere auf Informationen, die für Einstiegsfragen in einem Interview relevant sind.

ZUSAMMENFASSUNG:"""

        try:
            # Nutze LLM für Zusammenfassung
            response = llm_client.chat(
                model="mistral-small-latest",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,  # Niedrige Temperature für faktische Zusammenfassung
                max_tokens=1500
            )
            
            summary = response.choices[0].message.content.strip()
            
            # Kürze falls nötig
            if len(summary) > max_summary_length:
                logger.debug(f"⚠️  Zusammenfassung zu lang ({len(summary)} Zeichen), kürze...")
                summary = summary[:max_summary_length] + "..."
            
            logger.info(f"✅ Dokument-Zusammenfassung generiert ({len(summary)} Zeichen)")
            logger.debug(f"📄 Zusammenfassung Vorschau: {summary[:200]}...")
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Generieren der Zusammenfassung: {str(e)}", exc_info=True)
            return ""
    
    def reset(self):
        """Setzt das RAG-System zurück."""
        logger.info("🔄 Setze RAG-System zurück...")
        self.vectorstore = None
        self.documents = []
        self.is_initialized = False
        logger.info("✅ RAG-System zurückgesetzt")
    
    def get_stats(self) -> Dict[str, Any]:
        """Gibt Statistiken über das RAG-System zurück."""
        return {
            'is_initialized': self.is_initialized,
            'num_documents': len(self.documents),
            'num_chunks': len(self.vectorstore.index_to_docstore_id) if self.vectorstore else 0,
            'embedding_model': self.embeddings.model_name if self.embeddings else None
        }
