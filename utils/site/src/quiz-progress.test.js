import test from 'node:test';
import assert from 'node:assert/strict';
import { QuizProgress } from './quiz-progress.js';

const fixture = () => new QuizProgress([
  { id: 'first', correct: 'B' }, { id: 'other', correct: 'C' }, { id: 'last', correct: 'A' },
]);

test('нет результата до выбора и проверки ответа', () => {
  const quiz = fixture();
  assert.equal(quiz.submit('first'), null);
  assert.equal(quiz.select('missing', 'A'), false);
  assert.equal(quiz.select('first', 'E'), false);
  quiz.select('first', 'B');
  assert.equal(quiz.summary.checked, 0);
  assert.deepEqual(quiz.submit('first'), { correct: true, selected: 'B' });
  assert.equal(quiz.select('first', 'A'), false);
  assert.equal(quiz.submit('first'), null);
  assert.deepEqual(quiz.summary, { total: 3, checked: 1, firstCorrect: 1, toRepeat: 0 });
});

test('повторная попытка сохраняет первый результат и не удваивает прогресс', () => {
  const quiz = fixture();
  quiz.select('first', 'A');
  quiz.submit('first');
  assert.equal(quiz.summary.toRepeat, 1);
  quiz.retry('first');
  assert.equal(quiz.answers.get('first').selected, null);
  quiz.select('first', 'B');
  quiz.submit('first');
  assert.deepEqual(quiz.summary, { total: 3, checked: 1, firstCorrect: 0, toRepeat: 0 });
  quiz.retry('first');
  quiz.select('first', 'A');
  quiz.submit('first');
  assert.equal(quiz.summary.firstCorrect, 0);
  assert.equal(quiz.summary.checked, 1);
  assert.equal(quiz.summary.toRepeat, 1);
});

test('навигация пропускает проверенные вопросы и возвращается к пропущенным', () => {
  const quiz = fixture();
  quiz.select('other', 'C');
  quiz.submit('other');
  assert.equal(quiz.nextUnchecked('first'), 'last');
  assert.equal(quiz.nextUnchecked('last'), 'first');
  quiz.select('first', 'B');
  quiz.submit('first');
  quiz.select('last', 'A');
  quiz.submit('last');
  assert.equal(quiz.nextUnchecked('last'), null);
  assert.equal(quiz.summary.firstCorrect, 3);
});

test('новый проход и независимая самопроверка начинают без прежних результатов', () => {
  const quiz = fixture();
  quiz.select('first', 'B');
  quiz.submit('first');
  assert.equal(fixture().summary.checked, 0);
  quiz.reset();
  assert.deepEqual(quiz.summary, { total: 3, checked: 0, firstCorrect: 0, toRepeat: 0 });
  assert.equal(quiz.answers.get('first').checked, false);
});
