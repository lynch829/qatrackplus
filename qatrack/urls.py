from django.conf import settings
from django.conf.urls.defaults import patterns, include, url
from django.views.generic.base import TemplateView

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',

    url(r'^$', TemplateView.as_view(template_name="homepage.html"), name="home"),

    url(r'^accounts/', include('qatrack.accounts.urls')),
    url(r'^qa/', include('qatrack.qa.urls')),
    url(r'^pracimprov/', include('qatrack.pim.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),

    url(r'^', include('genericdropdown.urls')),

)

if settings.DEBUG:
    urlpatterns += patterns('',
        (r'^%s(?P<path>.*)$' % settings.MEDIA_URL[1:],
         'django.views.static.serve',
         {'document_root': settings.MEDIA_ROOT, 'show_indexes': True}),
    )
