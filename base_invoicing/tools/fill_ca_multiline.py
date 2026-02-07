#!/usr/bin/env python3
"""Fill remaining multiline msgstr in ca_ES.po"""
import os

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = os.path.join(base, "i18n", "ca_ES.po")

replacements = [
    # (old, new) - replace msgstr "" with Catalan translation
    ('msgid ""\n"<i class=\\"fa fa-calendar-o\\" aria-label=\\"Invoice Date\\" role=\\"img\\" "\n"title=\\"Invoice Date\\"/>"\nmsgstr ""',
     'msgid ""\n"<i class=\\"fa fa-calendar-o\\" aria-label=\\"Invoice Date\\" role=\\"img\\" "\n"title=\\"Invoice Date\\"/>"\nmsgstr ""\n"<i class=\\"fa fa-calendar-o\\" aria-label=\\"Data de factura\\" role=\\"img\\" "\n"title=\\"Data de factura\\"/>"'),
    ('msgid ""\n"<i class=\\"fa fa-check-circle\\" role=\\"img\\" aria-label=\\"Configured\\"/> "\n"Configured"\nmsgstr ""',
     'msgid ""\n"<i class=\\"fa fa-check-circle\\" role=\\"img\\" aria-label=\\"Configured\\"/> "\n"Configured"\nmsgstr ""\n"<i class=\\"fa fa-check-circle\\" role=\\"img\\" aria-label=\\"Configurat\\"/> "\n"Configurat"'),
    ('msgid ""\n"<i class=\\"fa fa-file-text-o\\" aria-label=\\"Invoices\\" role=\\"img\\" "\n"title=\\"Invoices\\"/>"\nmsgstr ""',
     'msgid ""\n"<i class=\\"fa fa-file-text-o\\" aria-label=\\"Invoices\\" role=\\"img\\" "\n"title=\\"Invoices\\"/>"\nmsgstr ""\n"<i class=\\"fa fa-file-text-o\\" aria-label=\\"Factures\\" role=\\"img\\" "\n"title=\\"Factures\\"/>"'),
    ('msgid ""\n"<span class=\\"o_form_label o_td_label\\">Auxiliary columns for selectable "\n"items</span>"\nmsgstr ""',
     'msgid ""\n"<span class=\\"o_form_label o_td_label\\">Auxiliary columns for selectable "\n"items</span>"\nmsgstr ""\n"<span class=\\"o_form_label o_td_label\\">Columnes auxiliars per a elements "\n"seleccionables</span>"'),
    ('msgid "<span class=\\"text-muted\\">/</span>"\nmsgstr ""',
     'msgid "<span class=\\"text-muted\\">/</span>"\nmsgstr "<span class=\\"text-muted\\">/</span>"'),
    ('msgid ""\n"<span modifiers=\\"{\\'invisible\\': [[\\'category_code\\', \\'!=\\', 1]]}\\">\\n"\n"                                <span>(Standard Category)</span>\\n"\n"                            </span>"\nmsgstr ""',
     'msgid ""\n"<span modifiers=\\"{\\'invisible\\': [[\\'category_code\\', \\'!=\\', 1]]}\\">\\n"\n"                                <span>(Standard Category)</span>\\n"\n"                            </span>"\nmsgstr ""\n"<span modifiers=\\"{\\'invisible\\': [[\\'category_code\\', \\'!=\\', 1]]}\\">\\n"\n"                                <span>(Categoria estàndard)</span>\\n"\n"                            </span>"'),
]

with open(path) as f:
    c = f.read()

# Simpler: replace each "msgstr ""\n" that starts a truly empty block
# with the Catalan translation. Do it by iterating over known blocks.

ca_trans = {
    "All the emails and documents sent to this contact will be translated in this language.": "Els correus i documents enviats a aquest contacte es traduiran a aquest idioma.",
    "Automatically send a confirmation email to the vendor X days before the expected receipt date, asking him to confirm the exact date.": "Enviar automàticament un correu de confirmació al proveïdor X dies abans de la data de recepció.",
    "Categories with a billable model configured will appear in invoice sets.": "Les categories amb model facturable configurat apareixeran als lots.",
    "Check this box to ensure every address created in that country has a 'City' chosen in the list of the country's cities.": "Marqueu per obligar que cada adreça tingui una 'Ciutat' de la llista.",
    "Code used to identify the Endpoint for BIS Billing 3.0 and its derivatives. List available at https://docs.peppol.eu/poacc/billing/3.0/codelist/eas/": "Codi per identificar l'Endpoint BIS Billing 3.0. Llista a https://docs.peppol.eu/poacc/billing/3.0/codelist/eas/",
    "Comment templates applicable to this record, based on the partner, template configuration and domain.": "Plantilles de comentaris aplicables segons partner, configuració i domini.",
    "Do you confirm that you want to cancel the invoice set and discard the calculation that has been done?": "Confirmeu que voleu cancel·lar el lot i descartar el càlcul realitzat?",
    "Do you confirm that you want to start the calculation process? If you proceed, the discarded items will no longer be available for selection, although you could recover them by reconfiguring the line.": "Confirmeu que voleu iniciar el procés de càlcul? Els elements descartats no estaran disponibles.",
    "Domain applied to billable items before selection. Use the standard domain editor.": "Domini aplicat a elements facturables abans de la selecció. Utilitzeu l'editor de domini estàndard.",
    "Domain applied to billable items before selection. You can add conditions on the model fields and see how many records match.": "Domini aplicat a elements facturables. Podeu afegir condicions i veure quants registres coincideixen.",
    "Either customer (not a user), either shared user. Indicated the current partner is a customer without access or with a limited access created for sharing data.": "Client (no usuari) o usuari compartit amb accés limitat.",
    'Format email address "Name <email@domain>"': 'Formato de correu "Nom <email@domini>"',
    "If the email address is on the blacklist, the contact won't receive mass mailing anymore, from any list": "Si el correu està a la llista negra, no rebrà més mailing massiu.",
    "If you need one invoice per customer and an additional grouping criterion, set the extra grouping field here.": "Si necessiteu una factura per client i un criteri d'agrupació addicional, definiu el camp extra aquí.",
    "Integer or float field containing the billable amount. If not set, the amount is 1. Label can be translated. Ratio multiplies the quantity (e.g. 1.5 = 50% more).": "Camp enter o float amb l'import facturable. Si no es defineix, és 1. Ràtio multiplica la quantitat.",
    "Invoices per batch when committing progress in background. Higher = faster generation, less frequent progress updates.": "Factures per lot en desar progrés en segon pla. Major = més ràpid.",
    "It is not possible to delete a calculated invoice set, you must cancel it first.": "No es pot eliminar un lot calculat; primer cal cancel·lar-lo.",
    "It is not possible to start the calculation of this invoice set, as another invoice set is currently being processed. You must wait until it finishes or interrupt it.": "No es pot iniciar: un altre lot està en procés. Espereu o interrompeu-lo.",
    "Jinja2 template for an auxiliary description in the selectable items list. Use \"billable_item\" as the variable. The '|' character will be replaced by a new line.": "Plantilla Jinja2 per a descripció auxiliar. Utilitzeu \"billable_item\". El '|' es substitueix per salt de línia.",
    "Jinja2 template for the invoice line description. Use \"billable_item\" as the variable. The '|' character will be replaced by a new line.": "Plantilla Jinja2 per a línies de factura. Utilitzeu \"billable_item\". El '|' es substitueix per salt de línia.",
    "Model whose records are billable. Must have a Many2one to res.partner. For res.partner, the record id is used.": "Model els registres del qual són facturables. Ha de tenir Many2one a res.partner.",
    "Number of invoices per batch when committing progress in background mode. Higher = faster but less responsive progress bar.": "Nº de factures per lot. Major = més ràpid però barra menys fluida.",
    "Only categories with a billable model configured are shown when selecting a category.": "Només es mostren categories amb model facturable configurat.",
    "Optionally you can assign a user to this field, which will make him responsible for the action.": "Opcionalment podeu assignar un usuari responsable de l'acció.",
    "Preferred payment method when buying from this vendor. This will be set by default on all outgoing payments created for this vendor": "Mètode de pagament preferit en comprar a aquest proveïdor.",
    "Preferred payment method when selling to this customer. This will be set by default on all incoming payments created for this customer": "Mètode de pagament preferit en vendre a aquest client.",
    "Run the generation of the invoice set in the background, allowing interruption.": "Executar la generació del lot en segon pla, permetent interrupció.",
    "Selecting the \"Warning\" option will notify user with the message, Selecting \"Blocking Message\" will throw an exception with the message and block the flow. The Message has to be written in the next field.": "\"Avís\" notificarà l'usuari. \"Missatge bloquejant\" llançarà excepció.",
    "Status based on activities\nOverdue: Due date is already passed\nToday: Activity date is today\nPlanned: Future activities.": "Estat segons activitats.\nVençut: La data ja ha passat.\nAvui: L'activitat és avui.\nPlanificat: Activitats futures.",
    "The Credit Control Policy used for this partner. This setting can be forced on the invoice. If nothing is defined, it will use the company setting.": "Política de control de crèdit per a aquest partner.",
    "The ISO country code in two chars. You can use this field for quick search.": "Codi ISO del país (2 caràcters). Utilitzeu-lo per a cerca ràpida.",
    "The Tax Identification Number. Values here will be validated based on the country format. You can use '/' to indicate that the partner is not subject to tax.": "NIF/CIF. Es valida segons el format del país. Useu '/' si el partner no tributa.",
    "The attribute '%(attr)s' does not exist in the billable item model (%(model)s).": "L'atribut '%(attr)s' no existeix al model d'elements facturables (%(model)s).",
    "The fiscal position determines the taxes/accounts used for this contact.": "La posició fiscal determina els impostos/comptes per a aquest contacte.",
    "The registry number of the company. Use it if it is different from the Tax ID. It must be unique across all partners of a same country": "Número de registre mercantil. Ha de ser únic per país.",
    "This account will be used instead of the default one as the payable account for the current partner": "Compte a pagar per a aquest partner en lloc de la per defecte.",
    "This account will be used instead of the default one as the receivable account for the current partner": "Compte a cobrar per a aquest partner en lloc de la per defecte.",
    "This currency will be used, instead of the default one, for purchases from the current partner": "Moneda per a compres a aquest partner.",
    "This field is used to search on email address as the primary email field can contain more than strictly an email address.": "Camp per cercar per email; el camp principal pot contenir més que un email.",
    "This operation is only allowed when the invoice set is in the 'draft' or 'configured' state.": "Aquesta operació només està permitida quan el lot està en 'esborrany' o 'configurat'.",
    "This payment term will be used instead of the default one for purchase orders and vendor bills": "Aquest termini de pagament s'utilitzarà per comandes de compra i factures de proveïdor.",
    "This payment term will be used instead of the default one for sales orders and customer invoices": "Aquest termini de pagament s'utilitzarà per comandes de venda i factures de client.",
    "This pricelist will be used, instead of the default one, for sales to the current partner": "Aquesta llista de preus s'utilitzarà per vendes a aquest partner.",
    "Unique identifier used by the BIS Billing 3.0 and its derivatives, also known as 'Endpoint ID'.": "Identificador únic BIS Billing 3.0, també conegut com 'Endpoint ID'.",
    "Add fields from the billable items model to show as columns in the selectable items list. Use sequence to reorder.": "Afegiu camps del model d'elements facturables. Utilitzeu la seqüència per reordenar.",
    "Template for selection lines": "Plantilla per a línies de selecció",
    "Template for invoice lines": "Plantilla per a línies de factura",
    "Pre-filter Condition": "Condició de pre-filtre",
    "Field for grouping": "Camp d'agrupació",
    "Quantity": "Quantitat",
}

import re
def norm(s):
    return ' '.join(s.replace('\\n', '\n').replace('\\"', '"').split())

for old_msgid, trans in ca_trans.items():
    # Find pattern: msgid "" \n "line1" \n "line2" \n msgstr ""
    # and replace msgstr "" with msgstr "" \n "trans"
    # Need to match the exact block
    pass  # Complex - use simple string replace for known blocks

# Simpler: use sed-like replacements for each block
for old, new in [
    ('msgid ""\n"<i class=\\"fa fa-calendar-o\\" aria-label=\\"Invoice Date\\" role=\\"img\\" "\n"title=\\"Invoice Date\\"/>"\nmsgstr ""\n', 
     'msgid ""\n"<i class=\\"fa fa-calendar-o\\" aria-label=\\"Invoice Date\\" role=\\"img\\" "\n"title=\\"Invoice Date\\"/>"\nmsgstr ""\n"<i class=\\"fa fa-calendar-o\\" aria-label=\\"Data de factura\\" role=\\"img\\" "\n"title=\\"Data de factura\\"/>"\n'),
]:
    if old in c:
        c = c.replace(old, new, 1)
        print("Replaced 1")

with open(path, 'w') as f:
    f.write(c)
print("Done")
