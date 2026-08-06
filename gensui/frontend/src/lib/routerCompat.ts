import { useCallback } from 'react';
import { useHistory } from 'react-router-dom';

export const useNavigate = () => {
  const history = useHistory();
  return useCallback((target: string, options?: { replace?: boolean }) => {
    if (options?.replace) history.replace(target);
    else history.push(target);
  }, [history]);
};
