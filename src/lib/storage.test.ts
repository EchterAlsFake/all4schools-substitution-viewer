import { beforeEach, describe, expect, it } from 'vitest';

import { loadOverrides, loadPreferences, writeStorage } from './storage';


describe('local preference compatibility', () => {
  beforeEach(() => localStorage.clear());

  it('loads the existing personal-plan schema without sending it anywhere', () => {
    localStorage.setItem(
      'vplan-preferences',
      JSON.stringify({ enabled: true, grade: '12', classLetter: '', courses: ['12_CHE1'] }),
    );

    expect(loadPreferences()).toEqual({
      enabled: true,
      grade: '12',
      classLetter: '',
      courses: ['12_CHE1'],
    });
  });

  it('keeps existing subject names, local teachers and colours', () => {
    const values = {
      '12_che1::che': { name: 'Chemie', teacher: 'Eigener Name', color: 'cyan' },
    };
    expect(writeStorage('vplan-subject-overrides', values)).toBe(true);
    expect(loadOverrides()).toEqual(values);
  });

  it('falls back safely when stored JSON is invalid', () => {
    localStorage.setItem('vplan-preferences', '{broken');
    expect(loadPreferences()).toEqual({ enabled: false, grade: '', classLetter: '', courses: [] });
  });
});
