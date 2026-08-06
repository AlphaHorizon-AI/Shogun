import { useCallback, useMemo } from 'react';
import { useHistory, useLocation } from 'react-router-dom';

type NavigateOptions = { replace?: boolean };

export const useNavigate = () => {
  const history = useHistory();
  return useCallback((target: string, options?: NavigateOptions) => {
    if (options?.replace) history.replace(target);
    else history.push(target);
  }, [history]);
};

export const useSearchParams = () => {
  const location = useLocation();
  const params = useMemo(() => new URLSearchParams(location.search), [location.search]);
  return [params] as const;
};
