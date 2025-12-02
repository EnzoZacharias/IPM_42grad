// Interview-Orchestrator Web-App JavaScript
// Leichtgewichtige Implementierung mit Streaming-Support und Session-Persistenz

class InterviewApp {
  constructor() {
    this.sessionId = this.getOrCreateSessionId();
    this.currentQuestion = null;
    this.useStreaming = true;  // Aktiviere Streaming für Fragen-Generierung
    this.init();
  }

  getOrCreateSessionId() {
    // Versuche Session-ID aus localStorage zu laden
    let sessionId = localStorage.getItem('interview_session_id');
    if (!sessionId) {
      sessionId = 'session_' + Date.now() + '_' +
          Math.random().toString(36).substr(2, 9);
      localStorage.setItem('interview_session_id', sessionId);
    }
    return sessionId;
  }

  generateSessionId() {
    return 'session_' + Date.now() + '_' +
        Math.random().toString(36).substr(2, 9);
  }

  async init() {
    this.setupEventListeners();
    this.setupBackendSelector();
    this.loadBackendStatus();
    this.loadUploadedFiles();

    // Prüfe ob eine gespeicherte Session existiert
    await this.checkForSavedSession();
  }

  async checkForSavedSession() {
    try {
      // Prüfe ob es gespeicherte Sessions gibt
      const response = await fetch('/api/sessions');
      const data = await response.json();

      if (data.success && data.sessions && data.sessions.length > 0) {
        // Prüfe ob aktuelle Session dabei ist
        const currentSession =
            data.sessions.find(s => s.session_id === this.sessionId);

        if (currentSession && currentSession.answered_questions > 0) {
          // Es gibt eine laufende Session - frage ob fortsetzen
          this.showSessionRestoreModal(currentSession, data.sessions);
        } else if (data.sessions.some(s => s.answered_questions > 0)) {
          // Es gibt andere Sessions mit Fortschritt
          this.showSessionRestoreModal(null, data.sessions);
        } else {
          // Keine relevanten Sessions - zeige Rollenauswahl
          this.showRoleSelection();
        }
      } else {
        // Keine Sessions vorhanden - zeige Rollenauswahl
        this.showRoleSelection();
      }
    } catch (error) {
      console.error('Error checking for saved sessions:', error);
      // Bei Fehler: zeige Rollenauswahl
      this.showRoleSelection();
    }
  }

  showSessionRestoreModal(currentSession, allSessions) {
    // Erstelle Modal-Dialog
    const modal = document.createElement('div');
    modal.className = 'session-modal';
    modal.id = 'session-restore-modal';

    let sessionsHtml = '';
    const relevantSessions = allSessions.filter(
        s => s.answered_questions > 0 ||
            (s.completed_interviews && s.completed_interviews > 0));

    for (const session of relevantSessions) {
      const date = new Date(session.last_activity);
      const dateStr = date.toLocaleDateString('de-DE') + ' ' +
          date.toLocaleTimeString(
              'de-DE', {hour: '2-digit', minute: '2-digit'});
      const isCurrent = session.session_id === this.sessionId;

      // Multi-Rollen Info
      const completedCount = session.completed_interviews || 0;
      const completedRolesStr =
          session.completed_roles && session.completed_roles.length > 0 ?
          session.completed_roles.join(', ') :
          '';

      sessionsHtml += `
        <div class="session-option ${
          isCurrent ? 'current' : ''}" data-session-id="${session.session_id}">
          <div class="session-info">
            <span class="session-role">${
          session.role || 'Noch nicht klassifiziert'}</span>
            <span class="session-date">${dateStr}</span>
          </div>
          <div class="session-progress">
            <span>${session.answered_questions} Fragen beantwortet</span>
            ${
          session.progress_percent !== undefined ?
              `<span class="progress-badge">${
                  session.progress_percent}%</span>` :
              ''}
          </div>
          ${
          completedCount > 0 ?
              `
          <div class="session-multi-roles">
            <span class="multi-roles-badge">📋 ${completedCount} Interview${
                  completedCount > 1 ? 's' : ''} abgeschlossen</span>
            ${
                  completedRolesStr ? `<span class="completed-roles-list">${
                                          completedRolesStr}</span>` :
                                      ''}
          </div>
          ` :
                                      ''                        }
          <div class="session-actions">
            <button class="btn-continue" onclick="app.continueSession('${
          session.session_id}')">Fortsetzen</button>
            <button class="btn-delete" onclick="app.deleteSession('${
          session.session_id}')">Löschen</button>
          </div>
        </div>
      `;
    }

    modal.innerHTML = `
      <div class="session-modal-content">
        <h3>💾 Gespeicherte Interviews gefunden</h3>
        <p>Sie haben laufende Interviews. Möchten Sie eines fortsetzen oder ein neues starten?</p>
        
        <div class="sessions-list">
          ${sessionsHtml}
        </div>
        
        <div class="modal-actions">
          <button class="btn-new" onclick="app.startNewSession()">Neues Interview starten</button>
        </div>
      </div>
    `;

    document.body.appendChild(modal);
  }

  closeSessionModal() {
    const modal = document.getElementById('session-restore-modal');
    if (modal) {
      modal.remove();
    }
  }

  async continueSession(sessionId) {
    try {
      this.showProcessStatus('Lade gespeicherte Session...');
      this.closeSessionModal();

      const response = await fetch('/api/sessions/resume', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_id: sessionId})
      });

      const data = await response.json();

      if (data.success) {
        // Aktualisiere Session-ID
        this.sessionId = sessionId;
        localStorage.setItem('interview_session_id', sessionId);

        // Stelle Chat-Verlauf wieder her
        this.restoreChatHistory(data.history);

        // Aktualisiere Status
        this.updateStatus(data.status);

        // Zeige die nächste Frage an
        if (data.current_question) {
          this.displayQuestion(data.current_question);
        }

        // Aktiviere Eingabefeld
        document.getElementById('answer-input').disabled = false;
        document.getElementById('answer-input').focus();

        this.hideProcessStatus();
        this.showSystemMessage(
            'Interview wurde wiederhergestellt. Sie können dort weitermachen, wo Sie aufgehört haben.');
      } else {
        this.hideProcessStatus();
        this.showSystemMessage(
            'Fehler beim Laden der Session: ' + data.message);
        await this.startInterview();
      }
    } catch (error) {
      console.error('Error continuing session:', error);
      this.hideProcessStatus();
      this.showSystemMessage('Fehler beim Laden der Session.');
      await this.startInterview();
    }
  }

  restoreChatHistory(history) {
    const chatMessages = document.getElementById('chat-messages');
    chatMessages.innerHTML = `
      <div class="welcome-message">
        <h3>Willkommen zurück!</h3>
        <p>Ihr Interview wurde wiederhergestellt.</p>
      </div>
    `;

    if (history && history.length > 0) {
      // Kompakte Zusammenfassung anzeigen
      const historyContainer = document.createElement('div');
      historyContainer.className = 'chat-history-summary';

      // Header mit Toggle
      const historyHeader = document.createElement('div');
      historyHeader.className = 'history-header';
      historyHeader.innerHTML = `
        <span class="history-title">📋 Bisherige Antworten (${
          history.length})</span>
        <button class="history-toggle-btn">Details anzeigen ▼</button>
      `;
      historyContainer.appendChild(historyHeader);

      // Kompakte Liste der Q&A Paare
      const historyContent = document.createElement('div');
      historyContent.className = 'history-content collapsed';

      for (const entry of history) {
        if (entry.question && entry.answer) {
          const qaItem = document.createElement('div');
          qaItem.className = 'history-qa-item';
          qaItem.innerHTML = `
            <div class="history-question">
              <span class="history-q-icon">❓</span>
              <span class="history-q-text">${
              this.escapeHtml(entry.question)}</span>
            </div>
            <div class="history-answer">
              <span class="history-a-icon">💬</span>
              <span class="history-a-text">${
              this.escapeHtml(entry.answer)}</span>
            </div>
          `;
          historyContent.appendChild(qaItem);
        }
      }

      historyContainer.appendChild(historyContent);
      chatMessages.appendChild(historyContainer);

      // Toggle-Funktionalität
      historyHeader.querySelector('.history-toggle-btn')
          .addEventListener('click', function() {
            historyContent.classList.toggle('collapsed');
            this.textContent = historyContent.classList.contains('collapsed') ?
                'Details anzeigen ▼' :
                'Details ausblenden ▲';
          });
    }

    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  async deleteSession(sessionId) {
    if (!confirm('Möchten Sie diese Session wirklich löschen?')) {
      return;
    }

    try {
      const response = await fetch(
          `/api/sessions/${sessionId}`,
          {method: 'DELETE', headers: {'Content-Type': 'application/json'}});

      const data = await response.json();

      if (data.success) {
        // Wenn aktuelle Session gelöscht wurde, neue erstellen
        if (sessionId === this.sessionId) {
          localStorage.removeItem('interview_session_id');
          this.sessionId = this.generateSessionId();
          localStorage.setItem('interview_session_id', this.sessionId);
        }

        // Modal aktualisieren oder schließen
        this.closeSessionModal();
        await this.checkForSavedSession();
      }
    } catch (error) {
      console.error('Error deleting session:', error);
      this.showSystemMessage('Fehler beim Löschen der Session.');
    }
  }

  async startNewSession() {
    this.closeSessionModal();

    // Neue Session-ID generieren
    localStorage.removeItem('interview_session_id');
    this.sessionId = this.generateSessionId();
    localStorage.setItem('interview_session_id', this.sessionId);

    // Chat leeren
    const chatMessages = document.getElementById('chat-messages');
    chatMessages.innerHTML = `
      <div class="welcome-message">
        <h3>Willkommen!</h3>
        <p>Ich helfe Ihnen dabei, Ihre Geschäftsprozesse zu dokumentieren.</p>
        <p>Bitte beantworten Sie die folgenden Fragen so detailliert wie möglich.</p>
      </div>
    `;

    // Starte neues Interview
    await this.startInterview();
  }

  setupEventListeners() {
    // Send-Button und Enter-Taste
    const sendBtn = document.getElementById('send-btn');
    const answerInput = document.getElementById('answer-input');

    sendBtn.addEventListener('click', () => this.submitAnswer());
    answerInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        this.submitAnswer();
      }
    });

    // Reset-Button
    document.getElementById('reset-btn').addEventListener('click', () => {
      if (confirm(
              'Möchten Sie das Interview wirklich neu starten? Alle bisherigen Antworten gehen verloren.')) {
        this.resetInterview();
      }
    });

    // PDF Export Button
    const exportPdfBtn = document.getElementById('export-pdf-btn');
    if (exportPdfBtn) {
      exportPdfBtn.addEventListener('click', () => this.exportPDF());
    }

    // Neue Rolle Button
    const newRoleBtn = document.getElementById('new-role-btn');
    if (newRoleBtn) {
      newRoleBtn.addEventListener('click', () => this.startNewRoleInterview());
    }

    // Rollen-Auswahl Buttons
    const roleButtons = document.querySelectorAll('.role-btn');
    roleButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const role = btn.dataset.role;
        this.startInterviewWithRole(role);
      });
    });

    // File Upload
    const fileInput = document.getElementById('file-input');
    const selectFilesBtn = document.getElementById('select-files-btn');
    const uploadArea = document.getElementById('upload-area');

    selectFilesBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      fileInput.click();
    });
    fileInput.addEventListener(
        'change', (e) => this.handleFileSelect(e.target.files));

    // Drag & Drop
    uploadArea.addEventListener('dragover', (e) => {
      e.preventDefault();
      uploadArea.classList.add('drag-over');
    });

    uploadArea.addEventListener('dragleave', () => {
      uploadArea.classList.remove('drag-over');
    });

    uploadArea.addEventListener('drop', (e) => {
      e.preventDefault();
      uploadArea.classList.remove('drag-over');
      this.handleFileSelect(e.dataTransfer.files);
    });

    uploadArea.addEventListener('click', (e) => {
      if (e.target.id !== 'select-files-btn') {
        fileInput.click();
      }
    });
  }

  showRoleSelection() {
    // Zeige Rollen-Auswahl an
    const roleSelection = document.getElementById('role-selection');
    if (roleSelection) {
      roleSelection.style.display = 'block';
    }
    // Verstecke die Eingabe bis Rolle gewählt
    const inputContainer = document.querySelector('.chat-input-container');
    if (inputContainer) {
      inputContainer.style.display = 'none';
    }
  }

  hideRoleSelection() {
    const roleSelection = document.getElementById('role-selection');
    if (roleSelection) {
      roleSelection.style.display = 'none';
    }
    const inputContainer = document.querySelector('.chat-input-container');
    if (inputContainer) {
      inputContainer.style.display = 'block';
    }
  }

  async startInterviewWithRole(role) {
    try {
      this.hideRoleSelection();
      this.showProcessStatus(
          role === 'auto' ?
              'Starte Interview mit automatischer Rollenerkennung...' :
              `Starte Interview für Rolle: ${role}...`);

      const response = await fetch('/api/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          session_id: this.sessionId,
          preset_role: role === 'auto' ? null : role
        })
      });

      const data = await response.json();

      if (data.success) {
        this.updateStatus(data.status);

        if (data.question) {
          this.displayQuestion(data.question);
        }

        this.hideProcessStatus();

        if (role !== 'auto') {
          this.showSystemMessage(
              `✅ Interview für "${this.getRoleLabel(role)}" gestartet.`);
        }
      } else {
        this.hideProcessStatus();
        this.showSystemMessage('❌ Fehler: ' + data.message);
      }
    } catch (error) {
      console.error('Error starting interview with role:', error);
      this.hideProcessStatus();
      this.showSystemMessage('❌ Fehler beim Starten des Interviews.');
    }
  }

  getRoleLabel(role) {
    const labels = {
      'fach': 'Fachabteilung',
      'it': 'IT-Abteilung',
      'management': 'Management'
    };
    return labels[role] || role;
  }

  async startInterview() {
    try {
      // Zeige Lade-Status
      this.showProcessStatus('Initialisiere Interview...');

      if (this.useStreaming) {
        await this.startInterviewWithStreaming();
      } else {
        await this.startInterviewNonStreaming();
      }
    } catch (error) {
      console.error('Error starting interview:', error);
      this.hideProcessStatus();
      this.showSystemMessage(
          'Fehler beim Starten des Interviews. Bitte laden Sie die Seite neu.');
    }
  }

  async startInterviewWithStreaming() {
    // Erstelle einen temporären Container für die gestreamte Frage
    const streamingContainer = this.createStreamingQuestionContainer();

    try {
      const response = await fetch('/api/next-question-stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({session_id: this.sessionId})
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let questionText = '';

      while (true) {
        const {value, done} = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === 'status') {
                this.showProcessStatus(data.message);
              } else if (data.type === 'chunk') {
                // Zeige Text-Chunk in Echtzeit
                questionText += data.text;
                this.updateStreamingQuestion(streamingContainer, questionText);
              } else if (data.type === 'complete') {
                this.hideProcessStatus();
                // Wandle Streaming-Container direkt in finale Frage um
                if (data.question) {
                  this.finalizeStreamingQuestion(
                      streamingContainer, data.question);
                  this.updateStatus(data.status);
                } else {
                  this.removeStreamingContainer(streamingContainer);
                }
              } else if (data.type === 'error') {
                this.hideProcessStatus();
                this.removeStreamingContainer(streamingContainer);
                this.showSystemMessage('Fehler: ' + data.message);
              }
            } catch (e) {
              // Ignoriere Parse-Fehler
            }
          }
        }
      }
    } catch (error) {
      this.removeStreamingContainer(streamingContainer);
      throw error;
    }
  }

  async startInterviewNonStreaming() {
    const response = await fetch('/api/start', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({session_id: this.sessionId})
    });

    const data = await response.json();

    if (data.success && data.question) {
      this.hideProcessStatus();
      this.displayQuestion(data.question);
      this.updateStatus(data.status);
    }
  }

  createStreamingQuestionContainer() {
    const chatMessages = document.getElementById('chat-messages');
    const container = document.createElement('div');
    container.className = 'message question streaming';
    container.id = 'streaming-question';
    container.innerHTML = `
      <div class="message-label">Frage</div>
      <div class="message-text streaming-text"><span class="cursor">|</span></div>
    `;
    chatMessages.appendChild(container);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return container;
  }

  updateStreamingQuestion(container, text) {
    if (!container) return;
    const textDiv = container.querySelector('.streaming-text');
    if (textDiv) {
      textDiv.innerHTML =
          this.escapeHtml(text) + '<span class="cursor">|</span>';
      const chatMessages = document.getElementById('chat-messages');
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }
  }

  finalizeStreamingQuestion(container, question) {
    // Wandle den Streaming-Container direkt in die finale Frage um
    if (!container || !question) return;

    // Entferne streaming-Klasse für finalen Look
    container.classList.remove('streaming');
    container.removeAttribute('id');

    // Aktualisiere Label
    const labelDiv = container.querySelector('.message-label');
    if (labelDiv) {
      labelDiv.textContent = 'Frage';
      labelDiv.style.animation = 'none';
    }

    // Aktualisiere Text (entferne Cursor)
    const textDiv = container.querySelector('.streaming-text');
    if (textDiv) {
      textDiv.className = 'message-text';
      textDiv.textContent = question.text;
    }

    // Setze aktuelle Frage
    this.currentQuestion = question;
    const currentQuestionDiv = document.getElementById('current-question');
    if (currentQuestionDiv) {
      currentQuestionDiv.textContent = question.text;
    }
  }

  removeStreamingContainer(container) {
    if (container && container.parentNode) {
      container.parentNode.removeChild(container);
    }
  }

  async submitAnswer() {
    const answerInput = document.getElementById('answer-input');
    const answer = answerInput.value.trim();

    if (!answer || !this.currentQuestion) {
      return;
    }

    // Zeige Antwort im Chat
    this.displayAnswer(answer);

    // Eingabefeld leeren und deaktivieren
    answerInput.value = '';
    answerInput.disabled = true;

    try {
      if (this.useStreaming) {
        await this.submitAnswerWithStreaming(answer);
      } else {
        await this.submitAnswerNonStreaming(answer);
      }
    } catch (error) {
      console.error('Error submitting answer:', error);
      this.hideProcessStatus();
      this.showSystemMessage(
          'Fehler beim Senden der Antwort. Bitte versuchen Sie es erneut.');
      document.getElementById('answer-input').disabled = false;
    }
  }

  async submitAnswerWithStreaming(answer) {
    this.showProcessStatus('Verarbeite Antwort...');

    // Erstelle Streaming-Container für nächste Frage
    const streamingContainer = this.createStreamingQuestionContainer();
    let questionText = '';

    try {
      const response = await fetch('/api/answer-stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: this.sessionId,
          question_id: this.currentQuestion.id,
          answer: answer
        })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      const answerInput = document.getElementById('answer-input');

      while (true) {
        const {value, done} = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === 'status') {
                this.showProcessStatus(data.message);
              } else if (data.type === 'chunk') {
                questionText += data.text;
                this.updateStreamingQuestion(streamingContainer, questionText);
              } else if (data.type === 'complete') {
                this.hideProcessStatus();
                this.updateStatus(data.status);

                if (data.completed) {
                  this.removeStreamingContainer(streamingContainer);
                  this.showSystemMessage(
                      'Interview abgeschlossen! Vielen Dank für Ihre Antworten.');
                  answerInput.disabled = true;
                } else if (data.question) {
                  // Wandle Streaming-Container direkt in finale Frage um
                  this.finalizeStreamingQuestion(
                      streamingContainer, data.question);
                  answerInput.disabled = false;
                  answerInput.focus();
                } else {
                  this.removeStreamingContainer(streamingContainer);
                }

                // Zeige Info wenn Rolle klassifiziert wurde
                if (data.role_classified && data.status?.role) {
                  const confidence = data.status.role_confidence_low ?
                      '(unsicher)' :
                      '(sicher)';
                  this.showSystemMessage(`Rolle identifiziert: ${
                      data.status.role_label} ${confidence}`);
                }
              } else if (data.type === 'error') {
                this.hideProcessStatus();
                this.removeStreamingContainer(streamingContainer);
                this.showSystemMessage('Fehler: ' + data.message);
                answerInput.disabled = false;
              }
            } catch (e) {
              // Ignoriere Parse-Fehler
            }
          }
        }
      }
    } catch (error) {
      this.removeStreamingContainer(streamingContainer);
      throw error;
    }
  }

  async submitAnswerNonStreaming(answer) {
    // Zeige Verarbeitungs-Status
    this.showProcessStatus('Verarbeite Antwort...');

    const response = await fetch('/api/answer', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_id: this.sessionId,
        question_id: this.currentQuestion.id,
        answer: answer
      })
    });

    const data = await response.json();
    const answerInput = document.getElementById('answer-input');

    if (data.success) {
      // Zeige spezifischen Prozess-Status falls vorhanden
      if (data.process_status) {
        this.showProcessStatus(data.process_status);
        // Kurze Verzögerung damit der User den Status sieht
        await new Promise(resolve => setTimeout(resolve, 800));
      }

      this.updateStatus(data.status);

      if (data.completed) {
        this.hideProcessStatus();
        this.showSystemMessage(
            'Interview abgeschlossen! Vielen Dank für Ihre Antworten.');
        answerInput.disabled = true;
      } else if (data.question) {
        this.hideProcessStatus();
        this.displayQuestion(data.question);
        answerInput.disabled = false;
        answerInput.focus();
      }
    }
  }

  displayQuestion(question) {
    this.currentQuestion = question;

    const chatMessages = document.getElementById('chat-messages');
    const currentQuestionDiv = document.getElementById('current-question');

    // Zeige Frage im Chat-Verlauf
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message question';

    let questionHtml = `<div class="message-label">Frage</div>`;
    questionHtml += `<div class="message-text">${question.text}</div>`;

    // Optionen werden nicht mehr angezeigt - User kann frei antworten

    messageDiv.innerHTML = questionHtml;
    chatMessages.appendChild(messageDiv);

    // Setze aktuelle Frage
    currentQuestionDiv.textContent = question.text;

    // Scroll nach unten
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  displayAnswer(answer) {
    const chatMessages = document.getElementById('chat-messages');

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message answer';
    messageDiv.innerHTML = `
            <div class="message-label">Ihre Antwort</div>
            <div class="message-text">${this.escapeHtml(answer)}</div>
        `;

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  showSystemMessage(message) {
    const chatMessages = document.getElementById('chat-messages');

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message system';
    messageDiv.innerHTML = `<div class="message-text">${message}</div>`;

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  async updateStatus(status = null) {
    if (!status) {
      try {
        const response =
            await fetch(`/api/status?session_id=${this.sessionId}`);
        const data = await response.json();
        if (data.success) {
          status = data.status;
        }
      } catch (error) {
        console.error('Error fetching status:', error);
        return;
      }
    }

    if (status) {
      document.getElementById('status-phase').textContent = status.phase_label;
      document.getElementById('status-role').textContent =
          status.role_name || status.role_label;
      document.getElementById('status-questions').textContent =
          status.answered_questions;
      document.getElementById('status-files').textContent =
          status.uploaded_files_count;

      // Hervorheben bei niedriger Konfidenz
      const roleElement = document.getElementById('status-role');
      if (status.role_confidence_low) {
        roleElement.style.color = '#ff9800';
        roleElement.title = 'Rollenzuordnung unsicher';
      } else {
        roleElement.style.color = '';
        roleElement.title = '';
      }

      // Fortschrittsanzeige aktualisieren
      this.updateProgressDisplay(status);

      // Multi-Rollen: Abgeschlossene Interviews anzeigen
      this.updateCompletedInterviews(status);
    }
  }

  updateCompletedInterviews(status) {
    const list = document.getElementById('completed-interviews-list');
    const section = document.getElementById('completed-interviews-section');
    const newRoleBtn = document.getElementById('new-role-btn');

    if (!list || !section) return;

    const completedRoles = status.completed_roles || [];
    const hasProgress = status.answered_questions > 0;
    const hasRole = status.role && status.role !== 'Undefiniert';
    const hasCompleted = completedRoles.length > 0;

    // Liste aktualisieren
    list.innerHTML = '';

    // Zeige abgeschlossene/gespeicherte Interviews (klickbar zum Wechseln)
    if (completedRoles.length > 0) {
      for (let i = 0; i < completedRoles.length; i++) {
        const interview = completedRoles[i];
        const li = document.createElement('li');
        li.className = 'completed-interview-item clickable';
        li.dataset.index = i;
        li.innerHTML = `
          <div class="completed-interview-info">
            <span class="completed-interview-status">${
            interview.is_current ? '📝' : '✅'}</span>
            <span class="completed-interview-role">${
            interview.role_label || interview.role || 'In Bearbeitung'}</span>
          </div>
          <div class="completed-interview-actions">
            <span class="completed-interview-progress">${
            interview.progress_percent || 0}%</span>
            <button class="btn-switch" title="Zu diesem Interview wechseln">→</button>
          </div>
        `;
        // Klick-Handler zum Wechseln
        li.addEventListener('click', () => this.switchToInterview(i));
        list.appendChild(li);
      }
    }

    // Aktuelles Interview anzeigen wenn es Fortschritt hat
    if (hasProgress && hasRole) {
      const currentLi = document.createElement('li');
      currentLi.className = 'completed-interview-item current-interview';
      currentLi.innerHTML = `
        <div class="completed-interview-info">
          <span class="completed-interview-status">📝</span>
          <span class="completed-interview-role">${
          status.role_label || status.role} (aktuell)</span>
        </div>
        <span class="completed-interview-progress">${
          status.progress?.percent || 0}%</span>
      `;
      list.appendChild(currentLi);
    }

    // Sektion anzeigen wenn abgeschlossene Interviews oder Fortschritt mit
    // erkannter Rolle
    if (hasCompleted || (hasProgress && hasRole)) {
      section.style.display = 'block';
    } else {
      section.style.display = 'none';
    }

    // "Neue Rolle" Button zeigen wenn aktuelles Interview Fortschritt hat
    // und eine Rolle erkannt wurde
    if (newRoleBtn) {
      if ((hasProgress && hasRole) || hasCompleted) {
        newRoleBtn.classList.add('visible');
      } else {
        newRoleBtn.classList.remove('visible');
      }
    }
  }

  async switchToInterview(interviewIndex) {
    const confirmMsg =
        'Möchten Sie zu diesem Interview wechseln?\n\nIhr aktueller Fortschritt wird gespeichert.';

    if (!confirm(confirmMsg)) {
      return;
    }

    try {
      this.showProcessStatus('Wechsle Interview...');

      const response = await fetch('/api/interview/switch', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(
            {session_id: this.sessionId, interview_index: interviewIndex})
      });

      const data = await response.json();

      if (data.success) {
        // Chat-Bereich leeren und Historie kompakt laden
        const chatMessages = document.getElementById('chat-messages');
        chatMessages.innerHTML = `
          <div class="welcome-message">
            <h3>Interview fortsetzen: ${
            data.switched_to?.role_label || 'Unbekannt'}</h3>
            <p>Sie können das Interview nun fortsetzen.</p>
          </div>
        `;

        // Chat-Historie als kompakte Zusammenfassung anzeigen
        if (data.chat_history && data.chat_history.length > 0) {
          const historyContainer = document.createElement('div');
          historyContainer.className = 'chat-history-summary';

          // Header mit Toggle
          const historyHeader = document.createElement('div');
          historyHeader.className = 'history-header';
          historyHeader.innerHTML = `
            <span class="history-title">📋 Bisherige Antworten (${
              Math.floor(data.chat_history.length / 2)})</span>
            <button class="history-toggle-btn">Details anzeigen ▼</button>
          `;
          historyContainer.appendChild(historyHeader);

          // Kompakte Liste der Q&A Paare
          const historyContent = document.createElement('div');
          historyContent.className = 'history-content collapsed';

          let currentQuestion = null;
          for (const item of data.chat_history) {
            if (item.type === 'question') {
              currentQuestion = item;
            } else if (item.type === 'answer' && currentQuestion) {
              const qaItem = document.createElement('div');
              qaItem.className = 'history-qa-item';
              qaItem.innerHTML = `
                <div class="history-question">
                  <span class="history-q-icon">❓</span>
                  <span class="history-q-text">${currentQuestion.text}</span>
                </div>
                <div class="history-answer">
                  <span class="history-a-icon">💬</span>
                  <span class="history-a-text">${item.text}</span>
                </div>
              `;
              historyContent.appendChild(qaItem);
              currentQuestion = null;
            }
          }

          historyContainer.appendChild(historyContent);
          chatMessages.appendChild(historyContainer);

          // Toggle-Funktionalität
          historyHeader.querySelector('.history-toggle-btn')
              .addEventListener('click', function() {
                historyContent.classList.toggle('collapsed');
                this.textContent =
                    historyContent.classList.contains('collapsed') ?
                    'Details anzeigen ▼' :
                    'Details ausblenden ▲';
              });
        }

        // Status aktualisieren
        this.updateStatus(data.status);

        // Nächste Frage anzeigen
        if (data.next_question) {
          this.displayQuestion(data.next_question);
        }

        // Eingabe aktivieren
        document.getElementById('answer-input').disabled = false;
        document.getElementById('answer-input').focus();

        this.hideProcessStatus();
        this.showSystemMessage(
            `✅ Gewechselt zu: ${data.switched_to?.role_label || 'Interview'}`);
      } else {
        this.hideProcessStatus();
        this.showSystemMessage('❌ Fehler: ' + data.message);
      }
    } catch (error) {
      console.error('Error switching interview:', error);
      this.hideProcessStatus();
      this.showSystemMessage('❌ Fehler beim Wechseln des Interviews.');
    }
  }

  async exportPDF() {
    // Prüfe ob Daten vorhanden
    const statusQuestions = document.getElementById('status-questions');
    const answeredCount = parseInt(statusQuestions?.textContent || '0');

    if (answeredCount === 0) {
      this.showSystemMessage(
          '⚠️ Keine Interview-Daten vorhanden. Bitte führen Sie zuerst ein Interview durch.');
      return;
    }

    try {
      this.showProcessStatus('Generiere PDF-Dokumentation...');

      const response = await fetch('/api/export/pdf', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_id: this.sessionId})
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || 'PDF-Generierung fehlgeschlagen');
      }

      // PDF als Blob empfangen
      const blob = await response.blob();

      // Download auslösen
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;

      // Dateiname aus Header oder Default
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = 'Prozessdokumentation.pdf';
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="(.+)"/);
        if (match) {
          filename = match[1];
        }
      }

      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      this.hideProcessStatus();
      this.showSystemMessage('✅ PDF-Dokumentation erfolgreich generiert!');

    } catch (error) {
      console.error('Error exporting PDF:', error);
      this.hideProcessStatus();
      this.showSystemMessage(
          '❌ Fehler bei der PDF-Generierung: ' + error.message);
    }
  }

  addQuestionToChat(text, themeName = null) {
    const chatMessages = document.getElementById('chat-messages');
    const questionDiv = document.createElement('div');
    questionDiv.className = 'chat-message question-message';

    let themeLabel =
        themeName ? `<span class="theme-label">${themeName}</span>` : '';
    questionDiv.innerHTML = `
      ${themeLabel}
      <div class="message-text">${text}</div>
    `;
    chatMessages.appendChild(questionDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  addAnswerToChat(text) {
    const chatMessages = document.getElementById('chat-messages');
    const answerDiv = document.createElement('div');
    answerDiv.className = 'chat-message answer-message';
    answerDiv.innerHTML = `<div class="message-text">${text}</div>`;
    chatMessages.appendChild(answerDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  async startNewRoleInterview() {
    const confirmMsg =
        'Möchten Sie ein neues Interview für eine andere Rolle starten?\n\n' +
        'Das aktuelle Interview wird gespeichert und Sie können eine neue Person befragen.';

    if (!confirm(confirmMsg)) {
      return;
    }

    try {
      this.showProcessStatus('Starte neues Rollen-Interview...');

      const response = await fetch('/api/interview/new', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_id: this.sessionId})
      });

      const data = await response.json();

      if (data.success) {
        // Chat leeren
        const chatMessages = document.getElementById('chat-messages');
        chatMessages.innerHTML = `
          <div class="welcome-message">
            <h3>Neues Interview</h3>
            <p>Sie können jetzt eine weitere Person befragen.</p>
            <p>Die Rolle wird automatisch anhand der Antworten erkannt.</p>
          </div>
        `;

        // Status aktualisieren
        this.updateStatus(data.status);

        // Erste Frage anzeigen
        if (data.question) {
          this.displayQuestion(data.question);
        }

        // Eingabe aktivieren
        document.getElementById('answer-input').disabled = false;
        document.getElementById('answer-input').focus();

        this.hideProcessStatus();
        this.showSystemMessage(`✅ Neues Interview gestartet. (${
            data.completed_interviews} vorherige Interviews gespeichert)`);
      } else {
        this.hideProcessStatus();
        this.showSystemMessage('❌ Fehler: ' + data.message);
      }
    } catch (error) {
      console.error('Error starting new role interview:', error);
      this.hideProcessStatus();
      this.showSystemMessage('❌ Fehler beim Starten des neuen Interviews.');
    }
  }

  updateProgressDisplay(status) {
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const progressDetail = document.getElementById('progress-detail');
    const themesProgress = document.getElementById('themes-progress');
    const themesList = document.getElementById('themes-list');

    if (!progressBar || !status.progress) return;

    const progress = status.progress;

    // Aktualisiere Fortschrittsbalken
    progressBar.style.width = `${progress.percent}%`;
    progressText.textContent = `${progress.percent}%`;
    progressDetail.textContent =
        `${progress.current} / ${progress.total} Pflichtfelder`;

    // Färbe Fortschrittsbalken basierend auf Status
    if (progress.is_complete) {
      progressBar.style.backgroundColor = '#4caf50';  // Grün
    } else if (progress.percent >= 50) {
      progressBar.style.backgroundColor = '#2196f3';  // Blau
    } else {
      progressBar.style.backgroundColor = '#ff9800';  // Orange
    }

    // Zeige Themenfelder nur bei rollenspezifischer Phase
    if (status.phase === 'role_specific' && progress.themes) {
      themesProgress.style.display = 'block';
      themesList.innerHTML = '';

      for (const [themeId, themeData] of Object.entries(progress.themes)) {
        const li = document.createElement('li');
        li.className = 'theme-item';

        const isComplete = themeData.required_filled === themeData.required;
        const statusIcon = isComplete ? '✅' : '⏳';
        const progressPercent = themeData.progress_percent;

        li.innerHTML = `
          <span class="theme-status">${statusIcon}</span>
          <span class="theme-name">${themeData.name}</span>
          <span class="theme-progress">${themeData.required_filled}/${
            themeData.required}</span>
          <div class="theme-progress-bar">
            <div class="theme-progress-fill" style="width: ${
            progressPercent}%"></div>
          </div>
        `;

        themesList.appendChild(li);
      }
    } else {
      themesProgress.style.display = 'none';
    }

    // Zeige Completion-Nachricht
    if (progress.is_complete) {
      this.showSystemMessage(
          '🎉 Interview abgeschlossen! Alle erforderlichen Informationen wurden erfasst.');
    }
  }

  async resetInterview() {
    try {
      this.showProcessStatus('Starte Interview neu...');

      // Lösche gespeicherte Session auf dem Server
      await fetch(
          `/api/sessions/${this.sessionId}`,
          {method: 'DELETE', headers: {'Content-Type': 'application/json'}});

      // Generiere neue Session-ID
      localStorage.removeItem('interview_session_id');
      this.sessionId = this.generateSessionId();
      localStorage.setItem('interview_session_id', this.sessionId);

      const response = await fetch('/api/reset', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({session_id: this.sessionId})
      });

      const data = await response.json();

      if (data.success) {
        // Lösche Chat-Verlauf
        const chatMessages = document.getElementById('chat-messages');
        chatMessages.innerHTML = `
                    <div class="welcome-message">
                        <h3>Willkommen!</h3>
                        <p>Ich helfe Ihnen dabei, Ihre Geschäftsprozesse zu dokumentieren.</p>
                        <p>Bitte beantworten Sie die folgenden Fragen so detailliert wie möglich.</p>
                    </div>
                `;

        // Aktiviere Eingabefeld
        document.getElementById('answer-input').disabled = false;
        document.getElementById('answer-input').focus();

        this.showSystemMessage('Interview wurde neu gestartet.');

        // Aktualisiere Status
        this.updateStatus(data.status);

        // Starte Interview mit Streaming
        if (this.useStreaming) {
          await this.startInterviewWithStreaming();
        } else if (data.question) {
          this.hideProcessStatus();
          this.displayQuestion(data.question);
        }
      }
    } catch (error) {
      console.error('Error resetting interview:', error);
      this.hideProcessStatus();
      this.showSystemMessage(
          'Fehler beim Zurücksetzen. Bitte laden Sie die Seite neu.');
    }
  }

  async handleFileSelect(files) {
    for (const file of files) {
      await this.uploadFile(file);
    }
  }

  async uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', this.sessionId);

    try {
      const response =
          await fetch('/api/upload', {method: 'POST', body: formData});

      const data = await response.json();

      if (data.success) {
        this.showSystemMessage(`Datei "${file.name}" wurde hochgeladen.`);
        this.addFileToList(data.file);
        this.updateStatus();
      } else {
        this.showSystemMessage(
            `Fehler beim Hochladen von "${file.name}": ${data.message}`);
      }
    } catch (error) {
      console.error('Error uploading file:', error);
      this.showSystemMessage(`Fehler beim Hochladen von "${file.name}".`);
    }
  }

  async loadUploadedFiles() {
    try {
      const response = await fetch(`/api/files?session_id=${this.sessionId}`);
      const data = await response.json();

      if (data.success && data.files.length > 0) {
        const filesList = document.getElementById('files-list');
        filesList.innerHTML = '';

        data.files.forEach(file => {
          this.addFileToList(file);
        });
      }
    } catch (error) {
      console.error('Error loading files:', error);
    }
  }

  addFileToList(file) {
    const filesList = document.getElementById('files-list');

    const li = document.createElement('li');
    li.className = 'file-item';

    const sizeKB = (file.size / 1024).toFixed(2);

    li.innerHTML = `
            <span class="file-icon">■</span>
            <div class="file-info">
                <div class="file-name">${this.escapeHtml(file.filename)}</div>
                <div class="file-size">${sizeKB} KB</div>
            </div>
        `;

    filesList.appendChild(li);
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  showProcessStatus(message) {
    const processActivity = document.getElementById('process-activity');
    const processMessage = document.getElementById('process-message');

    processMessage.textContent = message;
    processActivity.style.display = 'block';
  }

  hideProcessStatus() {
    const processActivity = document.getElementById('process-activity');
    processActivity.style.display = 'none';
  }

  // ==================== LLM Backend Management ====================

  setupBackendSelector() {
    const backendRadios =
        document.querySelectorAll('input[name="llm-backend"]');
    backendRadios.forEach(radio => {
      radio.addEventListener(
          'change', (e) => this.switchBackend(e.target.value));
    });
  }

  async loadBackendStatus() {
    try {
      const response =
          await fetch(`/api/llm/status?session_id=${this.sessionId}`);
      const data = await response.json();

      if (data.success) {
        this.updateBackendUI(data.status);
      }
    } catch (error) {
      console.error('Error loading backend status:', error);
    }
  }

  updateBackendUI(status) {
    // Update Status-Indikatoren
    const localStatus = document.getElementById('local-status');
    const apiStatus = document.getElementById('api-status');
    const currentModel = document.getElementById('current-model');

    if (localStatus) {
      localStatus.textContent = status.local.available ? '✅' : '❌';
      localStatus.className = 'backend-status ' +
          (status.local.available ? 'available' : 'unavailable');
    }

    if (apiStatus) {
      apiStatus.textContent = status.mistral_api.has_key ? '✅' : '❌';
      apiStatus.className = 'backend-status ' +
          (status.mistral_api.has_key ? 'available' : 'unavailable');
    }

    // Update aktuelles Modell
    if (currentModel) {
      if (status.current === 'local') {
        currentModel.textContent = status.local.model;
      } else {
        currentModel.textContent = status.mistral_api.model;
      }
    }

    // Update Radio-Button Auswahl
    const currentRadio = document.querySelector(
        `input[name="llm-backend"][value="${status.current}"]`);
    if (currentRadio) {
      currentRadio.checked = true;
    }
  }

  async switchBackend(backend) {
    try {
      this.showProcessStatus(`Wechsle zu ${
          backend === 'local' ? 'lokalem Modell' : 'Mistral API'}...`);

      const response = await fetch('/api/llm/switch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({session_id: this.sessionId, backend: backend})
      });

      const data = await response.json();

      if (data.success) {
        this.updateBackendUI(data.status);
        this.showSystemMessage(`✅ Backend gewechselt: ${
            backend === 'local' ? 'Lokales Modell' : 'Mistral API'}`);
      } else {
        // Bei Fehler: Radio auf aktuellen Wert zurücksetzen
        const currentRadio = document.querySelector(
            `input[name="llm-backend"][value="${data.status.current}"]`);
        if (currentRadio) {
          currentRadio.checked = true;
        }
        this.showSystemMessage(
            `⚠️ Backend-Wechsel fehlgeschlagen: ${data.message}`);
      }

      this.hideProcessStatus();
    } catch (error) {
      console.error('Error switching backend:', error);
      this.hideProcessStatus();
      this.showSystemMessage('❌ Fehler beim Backend-Wechsel');
      // Backend-Status neu laden um UI zu korrigieren
      this.loadBackendStatus();
    }
  }
}

// Starte die App wenn DOM geladen ist
document.addEventListener('DOMContentLoaded', () => {
  window.app = new InterviewApp();
});
