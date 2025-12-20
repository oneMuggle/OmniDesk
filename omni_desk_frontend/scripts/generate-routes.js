const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const fs = require('fs');
const path = require('path');

// Make paths relative to the script file to avoid issues with CWD
const routesFilePath = path.resolve(__dirname, '../src/routes/index.js');
const outputFilePath = path.resolve(__dirname, '../public/routes.json');

const code = fs.readFileSync(routesFilePath, 'utf-8');

const ast = parser.parse(code, {
  sourceType: 'module',
  plugins: ['jsx'],
});

const protectedRoutes = [];

function getAttributeValue(attributes, attrName) {
    const attr = attributes.find(a => a.name && a.name.name === attrName);
    if (!attr) return null;
    if (attr.value.type === 'StringLiteral') {
        return attr.value.value;
    }
    return null;
}

function processRouteObject(routeObject, parentPath) {
    if (!routeObject || routeObject.type !== 'ObjectExpression') return;

    const pathProp = routeObject.properties.find(p => p.key.name === 'path');
    const indexProp = routeObject.properties.find(p => p.key.name === 'index');
    const elementProp = routeObject.properties.find(p => p.key.name === 'element');
    const childrenProp = routeObject.properties.find(p => p.key.name === 'children');

    let currentPath = parentPath;
    if (pathProp && pathProp.value.type === 'StringLiteral') {
        currentPath = path.posix.join(parentPath, pathProp.value.value);
    }

    if (elementProp && elementProp.value.type === 'JSXElement') {
        const jsxElement = elementProp.value;
        const openingElement = jsxElement.openingElement;

        if (openingElement.name.name === 'ProtectedRoute') {
            const pageName = getAttributeValue(openingElement.attributes, 'pageName');
            const pagePath = getAttributeValue(openingElement.attributes, 'pagePath');
            const componentChild = jsxElement.children.find(child => child.type === 'JSXElement');

            if (pageName && componentChild) {
                const componentName = componentChild.openingElement.name.name;
                
                let routePath = pagePath;
                if (!routePath) {
                    if (indexProp && indexProp.value.value === true) {
                        routePath = parentPath;
                    } else {
                        routePath = currentPath;
                    }
                }
                
                if (!routePath.startsWith('/')) {
                    routePath = '/' + routePath;
                }

                protectedRoutes.push({
                    name: pageName,
                    path: routePath,
                    component: componentName,
                });
            }
        }
    }

    if (childrenProp && childrenProp.value.type === 'ArrayExpression') {
        childrenProp.value.elements.forEach(childRoute => {
            processRouteObject(childRoute, currentPath);
        });
    }
}


traverse(ast, {
  CallExpression(path) {
    if (path.node.callee.name === 'createBrowserRouter') {
      const routesArray = path.node.arguments[0];
      if (routesArray && routesArray.type === 'ArrayExpression') {
        routesArray.elements.forEach(routeObject => {
            processRouteObject(routeObject, '/');
        });
      }
    }
  },
});

// Remove duplicates
const uniqueRoutes = protectedRoutes.filter((v,i,a)=>a.findIndex(t=>(t.path === v.path && t.name === v.name))===i)

fs.writeFileSync(outputFilePath, JSON.stringify(uniqueRoutes, null, 2));

console.log(`Successfully generated routes.json with ${uniqueRoutes.length} routes!`);