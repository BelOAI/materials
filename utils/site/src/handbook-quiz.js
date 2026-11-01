// Progress is deliberately local to the current page; the source contains the answer.
export function enhanceQuizzes(root = document) {
  for (const quiz of root.querySelectorAll('.handbook-question:not([data-enhanced])')) {
    const button = quiz.querySelector('.quiz-check');
    const solution = quiz.querySelector('.quiz-solution');
    const result = quiz.querySelector('.quiz-result');
    quiz.dataset.enhanced = 'true';
    solution.hidden = true;
    button.hidden = false;
    quiz.addEventListener('change', () => {
      button.disabled = !quiz.querySelector('input:checked');
      solution.hidden = true;
      solution.open = false;
      result.textContent = '';
    });
    button.addEventListener('click', () => {
      const selected = quiz.querySelector('input:checked');
      if (!selected) return;
      result.textContent = selected.value === quiz.dataset.correct
        ? 'Верно. Сравните своё объяснение с решением.'
        : 'Пока неверно. Посмотрите подсказку или разберите решение и попробуйте снова.';
      solution.hidden = false;
      solution.open = true;
    });
  }
}
if (typeof document !== 'undefined') enhanceQuizzes();
