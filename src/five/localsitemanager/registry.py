import Acquisition
from zope.app.component.hooks import getSite
from zope.component.interfaces import ComponentLookupError
from zope.component.persistentregistry import PersistentAdapterRegistry
from zope.component.persistentregistry import PersistentComponents
from zope.interface.adapter import VerifyingAdapterLookup
from zope.interface.adapter import _lookup
from zope.interface.adapter import _lookupAll
from zope.interface.adapter import _subscriptions
import OFS.ObjectManager

_marker = object()

class FiveVerifyingAdapterLookup(VerifyingAdapterLookup):

    def _uncached_lookup(self, required, provided, name=u''):
        result = None
        order = len(required)
        for registry in self._registry.ro:
            byorder = registry._adapters
            if order >= len(byorder):
                continue

            extendors = registry._v_lookup._extendors.get(provided)
            if not extendors:
                continue

            components = byorder[order]
            result = _lookup(components, required, extendors, name, 0,
                             order)
            if result is not None:
                result = _wrap(result, registry)
                break

        self._subscribe(*required)

        return result

    def _uncached_lookupAll(self, required, provided):
        order = len(required)
        result = {}
        for registry in reversed(self._registry.ro):
            byorder = registry._adapters
            if order >= len(byorder):
                continue
            extendors = registry._v_lookup._extendors.get(provided)
            if not extendors:
                continue
            components = byorder[order]
            tmp_result = {}
            _lookupAll(components, required, extendors, tmp_result, 0, order)
            for k, v in tmp_result.iteritems():
                tmp_result[k] = _wrap(v, registry)
            result.update(tmp_result)

        self._subscribe(*required)

        return tuple(result.iteritems())

    def _uncached_subscriptions(self, required, provided):
        order = len(required)
        result = []
        for registry in reversed(self._registry.ro):
            byorder = registry._subscribers
            if order >= len(byorder):
                continue

            if provided is None:
                extendors = (provided, )
            else:
                extendors = registry._v_lookup._extendors.get(provided)
                if extendors is None:
                    continue

            _subscriptions(byorder[order], required, extendors, u'',
                           result, 0, order)

        self._subscribe(*required)

        return result


class FivePersistentAdapterRegistry(PersistentAdapterRegistry):

    LookupClass = FiveVerifyingAdapterLookup

def _wrap(comp, registry):
    """Return an aq wrapped component with the site as the parent but
    only if the comp has an aq wrapper to begin with.
    """

    # BBB: The primary reason for doing this sort of wrapping of
    # returned utilities is to support CMF tool-like functionality where
    # a tool expects it's aq_parent to be the portal object.  New code
    # (ie new utilities) should not rely on this predictability to
    # get the portal object and should search out an alternate means
    # (possibly retrieve the ISiteRoot utility).  Although in most
    # cases getting at the portal object shouldn't be the required pattern
    # but instead looking up required functionality via other (possibly
    # local) components.

    if Acquisition.interfaces.IAcquirer.providedBy(comp):
        parent = getSite()
        if parent is None:
            raise ValueError('Not enough context to acquire parent')

        base = Acquisition.aq_base(comp)

        if base is not Acquisition.aq_base(parent):
            # If the component is not the cmoponent registry container,
            # wrap it in the parent
            comp = base.__of__(parent)
        else:
            # If the component happens to be the component registry
            # container we are looking up a ISiteRoot.
            # We are not wrapping it in itself but in its own parent
            comp = base.__of__(Acquisition.aq_parent(parent))

    return comp

class PersistentComponents \
          (PersistentComponents,
           OFS.ObjectManager.ObjectManager):
    """An implementation of a component registry that can be persisted
    and looks like a standard ObjectManager.  It also ensures that all
    utilities have the the parent of this site manager (which should be
    the ISite) as their acquired parent.
    """

    def _init_registries(self):
        self.adapters = PersistentAdapterRegistry()
        self.utilities = FivePersistentAdapterRegistry()
