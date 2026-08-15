import { Suspense } from 'react';
import PropTypes from 'prop-types';
import PageSuspenseFallback from '../shared/components/PageSuspenseFallback';

const LazyComponent = ({ component: Component, ...props }) => (
  <Suspense fallback={<PageSuspenseFallback />}>
    <Component {...props} />
  </Suspense>
);

LazyComponent.propTypes = {
  component: PropTypes.elementType.isRequired,
};

export default LazyComponent;
