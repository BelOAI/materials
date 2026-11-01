// Session-only progress; retries cannot overwrite the first-attempt result.
export class QuizProgress {
  constructor(questions) {
    this.questions = questions;
    this.reset();
  }

  reset() {
    this.answers = new Map(this.questions.map(({ id }) => [id, {
      selected: null, checked: false, attempts: 0, firstCorrect: null, lastCorrect: null,
    }]));
  }

  select(id, value) {
    const answer = this.answers.get(id);
    if (!answer || answer.checked || !['A', 'B', 'C', 'D'].includes(value)) return false;
    answer.selected = value;
    return true;
  }

  submit(id) {
    const answer = this.answers.get(id);
    if (!answer?.selected || answer.checked) return null;
    const correct = answer.selected === this.questions.find(q => q.id === id).correct;
    answer.checked = true;
    answer.attempts++;
    answer.firstCorrect ??= correct;
    answer.lastCorrect = correct;
    return { correct, selected: answer.selected };
  }

  retry(id) {
    const answer = this.answers.get(id);
    if (!answer) return;
    answer.selected = null;
    answer.checked = false;
  }

  get summary() {
    const answers = [...this.answers.values()];
    return {
      total: answers.length,
      checked: answers.filter(a => a.attempts > 0).length,
      firstCorrect: answers.filter(a => a.firstCorrect === true).length,
      toRepeat: answers.filter(a => a.lastCorrect === false).length,
    };
  }

  nextUnchecked(id) {
    const index = this.questions.findIndex(q => q.id === id);
    const ordered = [...this.questions.slice(index + 1), ...this.questions.slice(0, index)];
    return ordered.find(q => this.answers.get(q.id).attempts === 0)?.id ?? null;
  }
}
