import { QuizProgress } from './quiz-progress.js';

// All questions remain readable in document order. No cookies or persistent scores.
export function enhanceQuizzes(root = document) {
  for (const group of root.querySelectorAll('.handbook-self-check:not([data-enhanced])')) {
    const questions = [...group.querySelectorAll('.handbook-question')];
    if (!questions.length) continue;
    const progress = new QuizProgress(questions.map(q => ({ id: q.id, correct: q.dataset.correct })));
    const byId = new Map(questions.map(q => [q.id, q]));
    const overview = group.querySelector('.quiz-overview');
    const summary = group.querySelector('.quiz-summary');
    const links = [...overview.querySelectorAll('.quiz-nav a')];
    const doc = group.ownerDocument;
    group.dataset.enhanced = 'true';

    function goTo(id) {
      const target = byId.get(id);
      if (!target) return;
      for (const link of links) {
        if (link.hash === '#' + id) link.setAttribute('aria-current', 'location');
        else link.removeAttribute('aria-current');
      }
      target.focus({ preventScroll: true });
      const reduceMotion = doc.defaultView.matchMedia('(prefers-reduced-motion: reduce)').matches;
      target.scrollIntoView({ behavior: reduceMotion ? 'instant' : 'smooth', block: 'start' });
    }

    function updateOverview() {
      const stats = progress.summary;
      overview.querySelector('.quiz-progress-text').textContent = `Проверено ${stats.checked} из ${stats.total}`;
      const bar = overview.querySelector('progress');
      bar.value = stats.checked;
      bar.textContent = `${stats.checked} из ${stats.total}`;
      for (const link of links) {
        const answer = progress.answers.get(link.hash.slice(1));
        const state = answer.lastCorrect === true ? 'correct' : answer.attempts ? 'incorrect' : 'unanswered';
        const label = state === 'correct' ? 'решён верно' : state === 'incorrect' ? 'нужно повторить' : 'ещё не проверен';
        link.dataset.state = state;
        link.setAttribute('aria-label', `Вопрос ${link.dataset.number}: ${label}`);
        link.querySelector('.quiz-nav-mark').textContent = state === 'correct' ? '✓' : state === 'incorrect' ? '↻' : '';
      }
      const complete = stats.checked === stats.total;
      summary.hidden = !complete;
      summary.querySelector('.quiz-score').textContent = `Верно с первой попытки: ${stats.firstCorrect} из ${stats.total}.`;
      summary.querySelector('.quiz-summary-note').textContent = stats.toRepeat
        ? 'Можно вернуться к вопросам с ошибками или пройти самопроверку заново.'
        : 'Все вопросы решены верно. Можно вернуться к объяснениям или продолжить чтение.';
      summary.querySelector('.quiz-review').hidden = !stats.toRepeat;
      for (const question of questions) {
        const next = question.querySelector('.quiz-next');
        next.textContent = progress.nextUnchecked(question.id) ? 'Следующий вопрос' : 'К результатам';
      }
    }

    function resetQuestion(question, closeHint = false) {
      for (const input of question.querySelectorAll('input[type="radio"]')) {
        input.checked = false;
        input.disabled = false;
      }
      for (const choice of question.querySelectorAll('.quiz-choice')) {
        delete choice.dataset.state;
        choice.querySelector('.quiz-choice-status').textContent = '';
      }
      const button = question.querySelector('.quiz-check');
      button.hidden = false;
      button.disabled = true;
      button.removeAttribute('aria-disabled');
      button.textContent = 'Проверить ответ';
      question.querySelector('.quiz-retry').hidden = true;
      question.querySelector('.quiz-next').hidden = true;
      const result = question.querySelector('.quiz-result');
      result.textContent = '';
      delete result.dataset.state;
      const solution = question.querySelector('.quiz-solution');
      solution.hidden = true;
      solution.open = false;
      if (closeHint) question.querySelector('.quiz-hint').open = false;
    }

    for (const question of questions) {
      // The status text is generated only for enhanced controls, never into sources.
      for (const choice of question.querySelectorAll('.quiz-choice')) {
        const status = doc.createElement('span');
        status.className = 'quiz-choice-status';
        choice.querySelector('label').append(status);
      }
      resetQuestion(question);
      question.addEventListener('change', event => {
        if (!event.target.matches('input[type="radio"]')) return;
        if (progress.select(question.id, event.target.value)) question.querySelector('.quiz-check').disabled = false;
      });
      question.querySelector('.quiz-check').addEventListener('click', () => {
        const outcome = progress.submit(question.id);
        if (!outcome) return;
        for (const choice of question.querySelectorAll('.quiz-choice')) {
          const input = choice.querySelector('input');
          input.disabled = true;
          if (input.value === question.dataset.correct) {
            choice.dataset.state = 'correct';
            choice.querySelector('.quiz-choice-status').textContent = outcome.correct ? 'Верно' : 'Правильный ответ';
          } else if (input.value === outcome.selected) {
            choice.dataset.state = 'incorrect';
            choice.querySelector('.quiz-choice-status').textContent = 'Ваш ответ · неверно';
          }
        }
        const result = question.querySelector('.quiz-result');
        result.dataset.state = outcome.correct ? 'correct' : 'incorrect';
        result.textContent = outcome.correct
          ? 'Верно. Сравните своё объяснение с решением.'
          : 'Пока неверно. Разберите решение и попробуйте ещё раз.';
        // Keep focus on the check button so keyboard users can continue in order.
        question.querySelector('.quiz-check').setAttribute('aria-disabled', 'true');
        question.querySelector('.quiz-check').textContent = 'Ответ проверен';
        question.querySelector('.quiz-retry').hidden = false;
        question.querySelector('.quiz-next').hidden = false;
        const solution = question.querySelector('.quiz-solution');
        solution.hidden = false;
        solution.open = true;
        updateOverview();
      });
      question.querySelector('.quiz-retry').addEventListener('click', () => {
        progress.retry(question.id);
        resetQuestion(question);
        question.querySelector('input').focus({ preventScroll: true });
      });
      question.querySelector('.quiz-next').addEventListener('click', () => {
        const nextId = progress.nextUnchecked(question.id);
        if (nextId) goTo(nextId);
        else {
          summary.hidden = false;
          summary.focus();
        }
      });
    }

    for (const link of links) link.addEventListener('click', event => {
      // Preserve normal open-in-new-tab and copy-link behaviour.
      if (event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      goTo(link.hash.slice(1));
    });
    group.querySelector('.quiz-restart').addEventListener('click', () => {
      progress.reset();
      for (const question of questions) resetQuestion(question, true);
      updateOverview();
      goTo(questions[0].id);
    });
    group.querySelector('.quiz-review').addEventListener('click', () => {
      const question = questions.find(q => {
        const answer = progress.answers.get(q.id);
        return answer.lastCorrect === false;
      });
      if (question) goTo(question.id);
    });
    updateOverview();
    overview.hidden = false;
  }
}
if (typeof document !== 'undefined') enhanceQuizzes();
