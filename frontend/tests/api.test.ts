import test from 'node:test';
import assert from 'node:assert/strict';

import { extractErrorMessage } from '../lib/api';

test('undefined → fallback', () => {
  assert.equal(extractErrorMessage(undefined), 'Запрос не выполнен');
});

test('undefined with custom fallback → custom fallback', () => {
  assert.equal(extractErrorMessage(undefined, 'custom'), 'custom');
});

test('string → returned as-is', () => {
  assert.equal(extractErrorMessage('simple error'), 'simple error');
});

test('{ detail: string } → detail string', () => {
  assert.equal(extractErrorMessage({ detail: 'text' }), 'text');
});

test('{ detail: { error: resume_limit_exceeded, limit } } → limit message', () => {
  const result = extractErrorMessage({ detail: { error: 'resume_limit_exceeded', limit: 2 } });
  assert.ok(result.includes('Достигнут лимит 2 профилей'), `got: ${result}`);
});

test('{ detail: { error, message } } → message wins', () => {
  assert.equal(
    extractErrorMessage({ detail: { error: 'something', message: 'human text' } }),
    'human text'
  );
});

test('{ detail: [{ loc, msg, type }] } → loc-prefixed msg', () => {
  const result = extractErrorMessage({
    detail: [
      {
        loc: ['body', 'email'],
        msg: 'value is not a valid email address',
        type: 'value_error'
      }
    ]
  });
  assert.ok(result.includes('email: value is not a valid email address'), `got: ${result}`);
});

test('{ detail: [multi] } → joined with "; "', () => {
  const result = extractErrorMessage({
    detail: [
      { loc: ['body', 'email'], msg: 'a' },
      { loc: ['body', 'password'], msg: 'b' }
    ]
  });
  assert.ok(result.includes('email: a'), `got: ${result}`);
  assert.ok(result.includes('password: b'), `got: ${result}`);
  assert.ok(result.includes('; '), `got: ${result}`);
});

test('{ error, message } top-level → message', () => {
  assert.equal(extractErrorMessage({ error: 'x', message: 'y' }), 'y');
});

test('empty object {} → fallback', () => {
  assert.equal(extractErrorMessage({}), 'Запрос не выполнен');
});
