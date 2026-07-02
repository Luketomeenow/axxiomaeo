<?php
/**
 * Plugin Name: Axxiom AEO Schema
 * Description: Registers aeo_schema_json for REST API and outputs JSON-LD in wp_head (Axxiom AEO Automation Platform).
 * Version: 1.1.1
 * Author: Axxiom Elevator
 *
 * Install: copy to wp-content/mu-plugins/axxiom-aeo-schema.php on each brand site.
 */

/**
 * Allow the Axxiom backend to write schema via WordPress REST API (meta.aeo_schema_json).
 */
add_action('init', function () {
    $args = [
        'type' => 'string',
        'single' => true,
        'show_in_rest' => true,
        'auth_callback' => function () {
            return current_user_can('edit_posts');
        },
    ];

    register_post_meta('post', 'aeo_schema_json', $args);
    register_post_meta('page', 'aeo_schema_json', $args);
});

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
    // '</' inside the JSON (e.g. '</script>' in a string) would end the block
    // early; '<\/' is a valid JSON escape, so the JSON-LD stays parseable.
    $schema = str_replace('</', '<\/', $schema);
    echo '<script type="application/ld+json">' . $schema . '</script>' . "\n";
}, 5);
