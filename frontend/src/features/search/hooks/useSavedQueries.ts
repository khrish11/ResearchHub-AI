import { useEffect, useState } from 'react';
import type { SavedQuery } from '../types';
import { SAVED_QUERIES_KEY, loadSavedQueries } from '../searchUtils';

export const useSavedQueries = () => {
  const [savedQueries, setSavedQueries] = useState<SavedQuery[]>(() => loadSavedQueries());

  useEffect(() => {
    localStorage.setItem(SAVED_QUERIES_KEY, JSON.stringify(savedQueries));
  }, [savedQueries]);

  return { savedQueries, setSavedQueries };
};
