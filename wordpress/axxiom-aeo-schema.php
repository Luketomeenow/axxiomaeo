<?php
/**
 * Plugin Name: Axxiom AEO Schema
 * Description: Outputs JSON-LD from post meta field aeo_schema_json (set by Axxiom AEO Automation Platform).
 * Version: 1.0.0
 * Author: Axxiom Elevator
 *
 * Install: copy to wp-content/mu-plugins/axxiom-aeo-schema.php on each brand site.
 */

add_action('wp_head', function () {
    if (!is_singular()) {
        return;
    }
    $post_id = get_queried_object_id();
    if (!$post_id) {
        return;
    }
    $schema = get_post_meta($post_id, 'aeo_schema_json', true);
    if (!$schema || !is_string($schema)) {
        return;
    }
    $schema = trim($schema);
    if ($schema === '') {
        return;
    }
    // Basic safety: only output if it looks like JSON object/array.
    if ($schema[0] !== '{' && $schema[0] !== '[') {
        return;
    }
    echo '<script type="application/ld+json">' . $schema . '</script>' . "\n";
}, 5);
